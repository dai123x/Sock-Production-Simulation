import simpy
import random
import matplotlib.pyplot as plt
import os

class HosieryLine:
    """袜业生产线仿真模型类"""
    def __init__(self, env, config):
        self.env = env
        self.config = config
        
        # 建立生产资源 (各个工序的机器/工人)
        self.seaming = simpy.Resource(env, capacity=config['seaming_machines'])
        self.sorting = simpy.Resource(env, capacity=config['sorting_machines'])
        self.shaping = simpy.Resource(env, capacity=config['shaping_machines'])
        self.tagging = simpy.Resource(env, capacity=config['tagging_machines'])
        self.packaging = simpy.Resource(env, capacity=config['packaging_machines'])

        # 数据追踪
        self.throughput = 0  # 产出量
        self.wip = 0         # 在制品数量 (Work In Progress)

    def process_sock(self, sock_id):
        """定义单双袜子经过整条流水线的流程"""
        self.wip += 1
        
        # 1. 缝头工序 (Seaming)
        with self.seaming.request() as req:
            yield req
            yield self.env.timeout(self.config['time_seaming'])

        # 2. 整理工序 (Sorting)
        with self.sorting.request() as req:
            yield req
            yield self.env.timeout(self.config['time_sorting'])

        # 3. 定型工序 (Shaping)
        with self.shaping.request() as req:
            yield req
            yield self.env.timeout(self.config['time_shaping'])

        # 4. 打签工序 (Tagging)
        with self.tagging.request() as req:
            yield req
            yield self.env.timeout(self.config['time_tagging'])

        # 5. 包装工序 (Packaging)
        with self.packaging.request() as req:
            yield req
            yield self.env.timeout(self.config['time_packaging'])

        # 加工完成
        self.wip -= 1
        self.throughput += 1

def sock_generator(env, line, inter_arrival_time):
    """袜子半成品产生器（模拟织造端送来的物料）"""
    sock_id = 0
    while True:
        # 指数分布模拟物料到达时间间隔
        yield env.timeout(random.expovariate(1.0 / inter_arrival_time))
        sock_id += 1
        env.process(line.process_sock(sock_id))

def run_simulation(config, simulation_time):
    """运行单一配置的仿真环境"""
    env = simpy.Environment()
    line = HosieryLine(env, config)
    env.process(sock_generator(env, line, config['inter_arrival_time']))
    env.run(until=simulation_time)
    return line

def generate_charts(line_before, line_after, lbr_before, lbr_after):
    """生成数据可视化对比图表"""
    plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
    plt.rcParams['axes.unicode_minus'] = False    # 用来正常显示负号

    labels = ['改善前 (孤岛式)', '改善后 (精益流水线)']
    throughputs = [line_before.throughput, line_after.throughput]
    lbrs = [lbr_before * 100, lbr_after * 100]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # 图表 1: 产能对比
    bars1 = ax1.bar(labels, throughputs, color=['#e74c3c', '#2ecc71'])
    ax1.set_title('日产能对比 (双/天)', fontsize=14)
    ax1.set_ylabel('产出数量', fontsize=12)
    for bar in bars1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 500, int(yval), ha='center', va='bottom', fontweight='bold', fontsize=12)

    # 图表 2: 线平衡率对比
    bars2 = ax2.bar(labels, lbrs, color=['#e67e22', '#3498db'])
    ax2.set_title('生产线平衡率 (LBR %)', fontsize=14)
    ax2.set_ylabel('百分比 (%)', fontsize=12)
    ax2.set_ylim(0, 100)
    for bar in bars2:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2.0, yval + 2, f"{yval:.1f}%", ha='center', va='bottom', fontweight='bold', fontsize=12)

    plt.tight_layout()
    chart_path = os.path.join(os.getcwd(), 'simulation_comparison.png')
    plt.savefig(chart_path, dpi=300)
    print(f"\n[成功] 效能对比图表已保存至: {chart_path}")


if __name__ == "__main__":
    # 模拟时间: 8小时排班 (28800 秒)
    SIM_TIME = 28800

    # ================= 改善前配置 (孤岛式生产) =================
    config_before = {
        'inter_arrival_time': 6.0,  # 约10件/分钟 (节拍6秒)
        'time_seaming': 6.0,        # 瓶颈工序耗时 6秒
        'time_sorting': 4.0,
        'time_shaping': 2.0,
        'time_tagging': 1.2,
        'time_packaging': 1.0,
        'seaming_machines': 1, 'sorting_machines': 1, 'shaping_machines': 1,
        'tagging_machines': 1, 'packaging_machines': 1,
    }

    # ================= 改善后配置 (精益流水线) =================
    config_after = {
        'inter_arrival_time': 1.33, # 约45件/分钟 (系统均衡流转)
        'time_seaming': 1.18,       # 自动化设备极大缩减缝头时间
        'time_sorting': 1.11,
        'time_shaping': 1.14,
        'time_tagging': 1.03,
        'time_packaging': 1.25,     # 新的瓶颈节拍 1.25秒
        'seaming_machines': 1, 'sorting_machines': 1, 'shaping_machines': 1,
        'tagging_machines': 1, 'packaging_machines': 1,
    }

    print("="*50)
    print("开始运行离散事件仿真 (SimPy)...")
    print("模拟时长: 8小时 (28800秒)")
    print("="*50)

    # 运行改善前仿真
    random.seed(42) # 固定随机数种子保证可复现性
    line_before = run_simulation(config_before, SIM_TIME)

    # 运行改善后仿真
    random.seed(42)
    line_after = run_simulation(config_after, SIM_TIME)

    # 计算生产线平衡率 (Line Balancing Rate)
    # 计算公式: 各工序时间总和 / (工序数 * 瓶颈工序时间)
    lbr_before = (6.0 + 4.0 + 2.0 + 1.2 + 1.0) / (5 * 6.0)
    lbr_after = (1.18 + 1.11 + 1.14 + 1.03 + 1.25) / (5 * 1.25)

    # 打印最终对比报告
    print("\n【仿真效能对比报告】")
    print(f"{'指标 (Metrics)':<25} | {'改善前 (孤岛式)':<15} | {'改善后 (流水线)':<15}")
    print("-" * 65)
    print(f"{'产出量 / Throughput (双)':<25} | {line_before.throughput:<15} | {line_after.throughput:<15}")
    print(f"{'在制品库存 / WIP (双)':<25} | {line_before.wip:<15} | {line_after.wip:<15}")
    print(f"{'线平衡率 / LBR (%)':<25} | {lbr_before*100:.1f}%{'':<11} | {lbr_after*100:.1f}%")
    print("-" * 65)

    # 生成图表
    generate_charts(line_before, line_after, lbr_before, lbr_after)
