# 袜业生产线精益优化与离散事件仿真项目 (Socks Production Simulation)

本项目将传统的工业工程（IE）精益生产案例代码化，使用 Python 的离散事件仿真库 `SimPy` 替代重型商业软件 FlexSim，实现对袜业生产线“优化前”与“优化后”的数字化仿真与效能对比分析。

## 目录结构
- `main_simulation.py`: 核心仿真代码，包含了流水线类 `HosieryLine` 以及改善前后的环境配置。
- `phd_level_simulation.py`: 扩展版仿真，输出更细分的效能指标与看板图表 `phd_analysis_dashboard.png`。
- `albp_milp_solver.py`: 装配线平衡问题（ALBP）的混合整数线性规划（MILP）求解器。
- `integrated_pipeline.py`: 一体化流水线——MILP 静态求解 → DES 动态仿真 → 经济性评价闭环，读取 `config.json` 配置，消除硬编码。
- `config.json`: 工序、节拍、先后约束等参数配置。
- `requirements.txt`: 运行仿真所需的 Python 依赖库。
- `simulation_comparison.png` / `phd_analysis_dashboard.png`: 运行仿真后自动生成的效能对比图表。

## 仿真逻辑说明
本项目模拟了一个标准 8 小时（28,800秒）工作班次内的生产情况。

### 1. 优化前（Before Optimization）
- **模式**：孤岛式作业，各工序间缺乏协同。
- **瓶颈节拍**：缝头工序耗时 6 秒/双。
- **系统表现**：由于前序物料到达速度与瓶颈工序严重不匹配，导致大量在制品（WIP）积压，整体线平衡率（LBR）极低（39.4%）。

### 2. 优化后（After Optimization）
- **模式**：U型流水线流转，采用全自动缝头机与多能工。
- **节拍重组**：瓶颈工序压缩至 1.25秒/双，各道工序节拍均衡（缝头1.18s, 整理1.11s, 定型1.14s, 打签1.03s, 包装1.25s）。
- **系统表现**：在制品库存大幅下降，设备无缝衔接，日产能飙升至约21,600双，线平衡率高达 90.1%。

## 如何运行
1. 安装依赖包（含运行 MILP 所需的 `pulp`）：
   ```bash
   pip install -r requirements.txt
   ```
2. 运行仿真脚本：
   ```bash
   python main_simulation.py
   ```
3. 查看控制台输出结果以及生成的对比图表 `simulation_comparison.png`。

## 扩展模块
- 一体化闭环评估（MILP + DES + 成本）：
  ```bash
  python integrated_pipeline.py
  ```
- 仅求解装配线平衡规划模型：
  ```bash
  python albp_milp_solver.py
  ```
