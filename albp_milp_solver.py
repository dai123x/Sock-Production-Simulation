import pulp

def solve_albp(tasks, processing_times, precedence_relations, cycle_time):
    """
    硕士学位论文核心算法：第一类装配线平衡问题 (ALBP-1) 的混合整数线性规划 (MILP) 模型
    目标：在给定节拍时间 (Cycle Time) 下，最小化工站数量 (Minimize number of workstations)。
    """
    num_tasks = len(tasks)
    # 理论最小工站数 与 最大工站数
    min_stations = int(sum(processing_times.values()) // cycle_time) + 1
    max_stations = num_tasks 

    # 初始化 MILP 模型
    prob = pulp.LpProblem("Assembly_Line_Balancing_Problem", pulp.LpMinimize)

    # 决策变量：x[i, j] = 1 表示任务 i 分配给工站 j
    x = pulp.LpVariable.dicts("x", 
                              ((i, j) for i in tasks for j in range(1, max_stations + 1)),
                              cat='Binary')
    
    # 决策变量：y[j] = 1 表示工站 j 被开启
    y = pulp.LpVariable.dicts("y", 
                              (j for j in range(1, max_stations + 1)),
                              cat='Binary')

    # 目标函数：最小化开启的工站数
    prob += pulp.lpSum([y[j] for j in range(1, max_stations + 1)])

    # 约束 1：唯一分配约束 (Occurrence Constraint)
    # 每个任务必须且只能被分配到一个工站
    for i in tasks:
        prob += pulp.lpSum([x[i, j] for j in range(1, max_stations + 1)]) == 1

    # 约束 2：节拍时间约束 (Cycle Time Constraint)
    # 每个工站分配的任务总时间不能超过给定节拍时间 c
    for j in range(1, max_stations + 1):
        prob += pulp.lpSum([processing_times[i] * x[i, j] for i in tasks]) <= cycle_time * y[j]

    # 约束 3：优先序约束 (Precedence Constraint)
    # 如果任务 u 必须在任务 v 之前完成，则 u 所在的工站编号必须小于等于 v 的工站编号
    for (u, v) in precedence_relations:
        prob += pulp.lpSum([j * x[u, j] for j in range(1, max_stations + 1)]) <= \
                pulp.lpSum([j * x[v, j] for j in range(1, max_stations + 1)])

    # 约束 4：工站顺序开启约束 (Station Order Constraint - 消除对称性，加速求解)
    for j in range(1, max_stations):
        prob += y[j+1] <= y[j]

    # 求解模型
    print("正在调用 CBC 求解器求解 ALBP MILP 模型...")
    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[prob.status] == 'Optimal':
        print(f"【最优解找到】最小所需工站数: {int(pulp.value(prob.objective))}")
        station_assignments = {}
        for j in range(1, max_stations + 1):
            if pulp.value(y[j]) == 1.0:
                assigned_tasks = [i for i in tasks if pulp.value(x[i, j]) == 1.0]
                station_assignments[j] = assigned_tasks
                load = sum(processing_times[t] for t in assigned_tasks)
                print(f"工站 {j} 分配任务: {assigned_tasks} | 负荷: {load:.2f}s | 闲置时间: {cycle_time - load:.2f}s")
    else:
        print("未找到最优解。")

if __name__ == "__main__":
    # 袜业生产线数据抽象
    tasks = ['织造', '缝头', '整理', '定型', '打签', '包装']
    # 加工时间 (秒)
    processing_times = {
        '织造': 0.14, '缝头': 1.18, '整理': 1.11, 
        '定型': 1.14, '打签': 1.03, '包装': 1.25
    }
    # 优先序约束 (前者必须在后者之前完成)
    precedence = [
        ('织造', '缝头'), ('缝头', '整理'), 
        ('整理', '定型'), ('定型', '打签'), 
        ('打签', '包装')
    ]
    # 目标节拍
    takt_time = 1.25 
    
    solve_albp(tasks, processing_times, precedence, takt_time)
