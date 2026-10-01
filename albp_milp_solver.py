import os

import pulp


def _cbc_solver(msg=0):
    solver = pulp.PULP_CBC_CMD(msg=msg)
    temp_dir = solver.tmpDir
    if temp_dir and not temp_dir.isascii():
        windows_dir = os.environ.get("WINDIR", r"C:\Windows")
        ascii_temp_dir = os.path.join(windows_dir, "Temp")
        if not os.path.isdir(ascii_temp_dir) or not os.access(ascii_temp_dir, os.W_OK):
            raise RuntimeError(
                "CBC cannot use the non-ASCII default temp path, and the ASCII "
                f"fallback directory is not writable: {ascii_temp_dir}"
            )
        solver.tmpDir = ascii_temp_dir
    return solver


def solve_albp(tasks, processing_times, precedence_relations, cycle_time):
    """
    硕士学位论文核心算法：第一类装配线平衡问题 (ALBP-1) 的混合整数线性规划 (MILP) 模型
    目标：在给定工位周期时间 (Cycle Time) 下，最小化工站数量 (Minimize number of workstations)。
    """
    num_tasks = len(tasks)
    max_stations = num_tasks 

    prob = pulp.LpProblem("Assembly_Line_Balancing_Problem", pulp.LpMinimize)

    x = pulp.LpVariable.dicts("x", 
                              ((i, j) for i in tasks for j in range(1, max_stations + 1)),
                              cat='Binary')
    
    y = pulp.LpVariable.dicts("y", 
                              (j for j in range(1, max_stations + 1)),
                              cat='Binary')

    prob += pulp.lpSum([y[j] for j in range(1, max_stations + 1)])

    for i in tasks:
        prob += pulp.lpSum([x[i, j] for j in range(1, max_stations + 1)]) == 1

    for j in range(1, max_stations + 1):
        prob += pulp.lpSum([processing_times[i] * x[i, j] for i in tasks]) <= cycle_time * y[j]

    for (u, v) in precedence_relations:
        prob += pulp.lpSum([j * x[u, j] for j in range(1, max_stations + 1)]) <= \
                pulp.lpSum([j * x[v, j] for j in range(1, max_stations + 1)])

    for j in range(1, max_stations):
        prob += y[j+1] <= y[j]

    print("正在调用 CBC 求解器求解 ALBP MILP 模型...")
    prob.solve(_cbc_solver(msg=0))

    if pulp.LpStatus[prob.status] == 'Optimal':
        optimal_stations = int(pulp.value(prob.objective))
        print(f"【最优解找到】最小所需工站数: {optimal_stations}")
        station_assignments = {}
        total_load = 0
        for j in range(1, max_stations + 1):
            if pulp.value(y[j]) == 1.0:
                assigned_tasks = [i for i in tasks if pulp.value(x[i, j]) == 1.0]
                station_assignments[j] = assigned_tasks
                load = sum(processing_times[t] for t in assigned_tasks)
                total_load += load
                print(f"工站 {j} 分配任务: {assigned_tasks} | 负荷: {load:.2f}s | 闲置时间: {cycle_time - load:.2f}s")
        
        lbr = total_load / (optimal_stations * cycle_time) * 100
        print(f"\n系统整体线平衡率 (LBR): {lbr:.2f}%")
    else:
        print("未找到最优解。")

if __name__ == "__main__":
    # 袜业主生产线数据抽象 (织造独立成列，不参与流水线平衡)
    tasks = ['缝头', '整理', '定型', '打签', '包装']
    processing_times = {
        '缝头': 1.18, '整理': 1.11, 
        '定型': 1.14, '打签': 1.03, '包装': 1.25
    }
    precedence = [
        ('缝头', '整理'), ('整理', '定型'), 
        ('定型', '打签'), ('打签', '包装')
    ]
    cycle_time = 1.25

    solve_albp(tasks, processing_times, precedence, cycle_time)
