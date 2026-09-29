import json
import pulp
import simpy
import numpy as np
import warnings

warnings.filterwarnings('ignore')

class IntegratedOptimizationPipeline:
    """
    顶级工程系统架构：运筹学静态求解(MILP) -> 离散事件动态仿真(DES) -> 经济指标评价(Cost)
    消除数据硬编码，实现自动化闭环评估。
    """
    def __init__(self, config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.optimal_stations = {}
        self.simulation_results = []

    def run_albp_milp(self):
        """阶段1：混合整数线性规划求解"""
        print("\n[Phase 1] 运行 MILP 装配线平衡优化...")
        tasks = list(self.config['tasks'].keys())
        proc_times = self.config['tasks']
        cycle_time = self.config['target_takt_time']
        precedence = self.config['precedence']
        
        max_stations = len(tasks)
        prob = pulp.LpProblem("ALBP", pulp.LpMinimize)
        x = pulp.LpVariable.dicts("x", ((i, j) for i in tasks for j in range(1, max_stations + 1)), cat='Binary')
        y = pulp.LpVariable.dicts("y", (j for j in range(1, max_stations + 1)), cat='Binary')

        prob += pulp.lpSum([y[j] for j in range(1, max_stations + 1)])

        for i in tasks:
            prob += pulp.lpSum([x[i, j] for j in range(1, max_stations + 1)]) == 1

        for j in range(1, max_stations + 1):
            prob += pulp.lpSum([proc_times[i] * x[i, j] for i in tasks]) <= cycle_time * y[j]

        for (u, v) in precedence:
            prob += pulp.lpSum([j * x[u, j] for j in range(1, max_stations + 1)]) <= \
                    pulp.lpSum([j * x[v, j] for j in range(1, max_stations + 1)])
        
        prob.solve(pulp.PULP_CBC_CMD(msg=0))
        
        if pulp.LpStatus[prob.status] == 'Optimal':
            self.num_stations = int(pulp.value(prob.objective))
            for j in range(1, max_stations + 1):
                if pulp.value(y[j]) == 1.0:
                    self.optimal_stations[f"Station_{j}"] = [i for i in tasks if pulp.value(x[i, j]) == 1.0]
            print(f"✅ 寻优成功！理论最小工站数: {self.num_stations}")
            for st, tks in self.optimal_stations.items():
                load = sum(proc_times[t] for t in tks)
                print(f"   {st}: 包含任务 {tks}, 负荷 {load:.2f}s (平衡损失率: {(cycle_time-load)/cycle_time*100:.1f}%)")
        else:
            raise ValueError("MILP 无法在给定节拍下找到可行解！")

    def run_des_simulation(self):
        """阶段2：依据 MILP 结果动态生成并运行仿真"""
        print("\n[Phase 2] 依据寻优结果自动构建数字孪生仿真模型...")
        
        def get_time(mu):
            cv = self.config['simulation']['stochastic_cv']
            return max(mu * 0.5, np.random.normal(mu, mu * cv))

        def sim_process(env, stations, results_dict):
            # 动态生成资源池
            resources = {st: simpy.Resource(env, capacity=1) for st in stations}
            wip = 0
            
            def process_item():
                nonlocal wip
                wip += 1
                for st, tasks in stations.items():
                    with resources[st].request() as req:
                        yield req
                        st_time = sum(self.config['tasks'][t] for t in tasks)
                        yield env.timeout(get_time(st_time))
                wip -= 1
                results_dict['throughput'] += 1

            def spawner():
                while True:
                    ia_time = self.config['target_takt_time']
                    yield env.timeout(get_time(ia_time))
                    env.process(process_item())
            
            # 每分钟记录WIP
            def monitor():
                while True:
                    results_dict['wip_log'].append(wip)
                    yield env.timeout(60)

            env.process(spawner())
            env.process(monitor())
        
        replications = self.config['simulation']['replications']
        for _ in range(replications):
            env = simpy.Environment()
            run_data = {'throughput': 0, 'wip_log': []}
            sim_process(env, self.optimal_stations, run_data)
            env.run(until=self.config['simulation']['shift_time_seconds'])
            self.simulation_results.append({
                'throughput': run_data['throughput'],
                'avg_wip': np.mean(run_data['wip_log'])
            })
        print(f"✅ {replications}次蒙特卡洛仿真完成！")

    def evaluate_financials(self):
        """阶段3：经济效益评价 (Financial & Cost Analysis)"""
        print("\n[Phase 3] 经济效益与 ROI 评价...")
        avg_tp = np.mean([r['throughput'] for r in self.simulation_results])
        avg_wip = np.mean([r['avg_wip'] for r in self.simulation_results])
        
        labor_cost = self.num_stations * self.config['financials']['labor_cost_per_station_per_shift']
        wip_cost = avg_wip * self.config['financials']['wip_holding_cost_per_unit']
        revenue = avg_tp * self.config['financials']['revenue_per_unit']
        net_profit = revenue - labor_cost - wip_cost
        
        print("-" * 50)
        print(f"指标 (平均值)\t\t| 金额 / 数量")
        print("-" * 50)
        print(f"最优所需人工工站数\t| {self.num_stations} 个")
        print(f"动态仿真班次产能\t| {avg_tp:.0f} 双")
        print(f"动态仿真平均在制品\t| {avg_wip:.1f} 双")
        print("-" * 50)
        print(f"班次人工成本 (C_labor)\t| ¥ {labor_cost:.2f}")
        print(f"在制品占用成本 (C_wip)\t| ¥ {wip_cost:.2f}")
        print(f"班次预期毛利 (Revenue)\t| ¥ {revenue:.2f}")
        print(f"班次净效益 (Net Profit)\t| ¥ {net_profit:.2f}")
        print("=" * 50)


if __name__ == "__main__":
    pipeline = IntegratedOptimizationPipeline("config.json")
    pipeline.run_albp_milp()
    pipeline.run_des_simulation()
    pipeline.evaluate_financials()
