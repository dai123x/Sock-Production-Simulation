import simpy
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import os
import warnings

warnings.filterwarnings('ignore')

def get_proc_time(mu, cv):
    """
    随机过程建模 (Stochastic Modeling)
    对正态随机抽样做下限裁切以避免过短的加工时间；这并非严格的截断正态抽样。
    该简化模型用于情景分析，不等同于真实工厂的校准分布。
    mu: 均值
    cv: 变异系数 (Coefficient of Variation) = 标准差 / 均值
    """
    if cv == 0:
        return mu
    sigma = mu * cv
    val = np.random.normal(mu, sigma)
    # 对抽样结果做下限裁切（clipping），不是重抽样意义上的截断正态分布。
    # 因此配置 CV 是输入波动参数，不等于裁切后的实际样本 CV。
    return max(val, mu * 0.5)

class PhDHosieryLine:
    """具备动态数据采集能力的仿真模型"""
    def __init__(self, env, config):
        self.env = env
        self.config = config
        
        self.seaming = simpy.Resource(env, capacity=1)
        self.sorting = simpy.Resource(env, capacity=1)
        self.shaping = simpy.Resource(env, capacity=1)
        self.tagging = simpy.Resource(env, capacity=1)
        self.packaging = simpy.Resource(env, capacity=1)

        self.throughput = 0
        self.wip = 0
        
        # 时序数据采集 (Time-series Data Collection)
        self.wip_log = []
        self.time_log = []
        
        env.process(self.monitor_wip())

    def monitor_wip(self):
        """周期性采样在制品库存，用于计算时间加权平均WIP"""
        while True:
            self.time_log.append(self.env.now)
            self.wip_log.append(self.wip)
            yield self.env.timeout(60) # 每分钟采样一次

    def process_sock(self):
        self.wip += 1
        cv = self.config['cv']
        
        with self.seaming.request() as req:
            yield req
            yield self.env.timeout(get_proc_time(self.config['t_seaming'], cv))
        
        with self.sorting.request() as req:
            yield req
            yield self.env.timeout(get_proc_time(self.config['t_sorting'], cv))

        with self.shaping.request() as req:
            yield req
            yield self.env.timeout(get_proc_time(self.config['t_shaping'], cv))

        with self.tagging.request() as req:
            yield req
            yield self.env.timeout(get_proc_time(self.config['t_tagging'], cv))

        with self.packaging.request() as req:
            yield req
            yield self.env.timeout(get_proc_time(self.config['t_packaging'], cv))

        self.wip -= 1
        self.throughput += 1

def sock_arrival(env, line, config):
    """到达间隔采用带下限裁切的正态抽样；这不是泊松到达过程。"""
    while True:
        yield env.timeout(get_proc_time(config['t_ia'], config['cv_ia']))
        env.process(line.process_sock())

def run_replication(config, sim_time=28800):
    """运行单次复制试验 (Single Replication)"""
    env = simpy.Environment()
    line = PhDHosieryLine(env, config)
    env.process(sock_arrival(env, line, config))
    env.run(until=sim_time)
    
    # 截去预热期 (Warm-up Period, 比如前60分钟) 数据以消除初始偏倚
    valid_wip = line.wip_log[60:] if len(line.wip_log) > 60 else line.wip_log
    avg_wip = np.mean(valid_wip) if valid_wip else 0
    
    return line.throughput, avg_wip

def monte_carlo_experiment(config_before, config_after, replications=30, sim_time=28800, seed=20261001):
    """
    通过多个独立场景运行获取样本分布。固定随机种子以便重现；相同的
    Replication 序号仅用于追踪运行次序，不表示前后场景使用配对随机数。
    """
    np.random.seed(seed)
    results = []

    print(f"正在执行蒙特卡洛仿真... (独立重复次数={replications}, seed={seed})")
    for i in range(replications):
        th_b, wip_b = run_replication(config_before, sim_time)
        results.append({
            'Replication': i + 1,
            'Scenario': 'Before (孤岛式)',
            'Throughput': th_b,
            'WIP': wip_b,
        })

        th_a, wip_a = run_replication(config_after, sim_time)
        results.append({
            'Replication': i + 1,
            'Scenario': 'After (精益化)',
            'Throughput': th_a,
            'WIP': wip_a,
        })

        if (i + 1) % 10 == 0:
            print(f"已完成 {i + 1}/{replications} 次试验")

    return pd.DataFrame(results)

def generate_academic_dashboard(df, t_stat_th, p_val_th):
    """
    情景仿真的结果可视化 (Scenario Simulation Visualization)
    使用核密度估计(KDE)和箱线图展示分布特性及置信区间。
    """
    plt.rcParams['font.sans-serif'] = ['SimHei'] 
    plt.rcParams['axes.unicode_minus'] = False
    
    sns.set_theme(style="whitegrid", font="SimHei")
    fig = plt.figure(figsize=(16, 8))
    fig.suptitle('袜业生产线情景仿真与统计摘要（DES）', fontsize=18, fontweight='bold', y=0.98)

    # 1. 产能分布的核密度估计图 (KDE Plot)
    ax1 = plt.subplot(1, 2, 1)
    sns.kdeplot(data=df, x="Throughput", hue="Scenario", fill=True, common_norm=False, palette="Set1", alpha=0.5, ax=ax1)
    ax1.set_title('8小时班次完成产量分布 (KDE)', fontsize=14)
    ax1.set_xlabel('班次完成产量 (双/8小时)', fontsize=12)
    ax1.set_ylabel('概率密度', fontsize=12)
    
    # 标注显著性检验结果
    significance_text = f"Welch 独立样本 t 检验（模拟）:\n$t = {t_stat_th:.2f}$\n$p = {p_val_th:.2e}$\n参数化情景输出；非现场因果证据"
    ax1.text(0.05, 0.95, significance_text, transform=ax1.transAxes, fontsize=11, 
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    # 2. 在制品库存的箱线图 (Boxplot)
    ax2 = plt.subplot(1, 2, 2)
    sns.boxplot(data=df, x="Scenario", y="WIP", palette="Set2", ax=ax2, showmeans=True, 
                meanprops={"marker":"o", "markerfacecolor":"white", "markeredgecolor":"black", "markersize":"8"})
    ax2.set_title('在制品(WIP)库存分布及其均值区间', fontsize=14)
    ax2.set_xlabel('系统场景', fontsize=12)
    ax2.set_ylabel('系统平均在制品数量 (双)', fontsize=12)

    plt.tight_layout()
    plt.subplots_adjust(top=0.90)
    project_dir = os.path.dirname(os.path.abspath(__file__))
    chart_path = os.path.join(project_dir, 'phd_analysis_dashboard.png')
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    print(f"\n[成功] 学术级仿真数据大屏已保存至: {chart_path}")

if __name__ == "__main__":
    SIM_TIME = 28800  # 8小时
    REPLICATIONS = 30
    RANDOM_SEED = 20261001

    # 孤岛式生产：极高的人工不稳定性 (CV较大)
    config_before = {
        't_ia': 6.0, 'cv_ia': 0.3, # 物料到达不稳定
        't_seaming': 6.0, 't_sorting': 4.0, 't_shaping': 2.0, 't_tagging': 1.2, 't_packaging': 1.0,
        'cv': 0.25 # 人工作业波动率 25%
    }

    # 参数化优化情景：设定更短的工序时间与较低的输入 CV；未模拟自动化改造过程
    config_after = {
        't_ia': 1.33, 'cv_ia': 0.05, # 物料平滑到达
        't_seaming': 1.18, 't_sorting': 1.11, 't_shaping': 1.14, 't_tagging': 1.03, 't_packaging': 1.25,
        'cv': 0.05 # 标准化及机器作业波动率仅 5%
    }

    # 运行蒙特卡洛仿真并保存每次运行的原始输出，便于复核报告统计量。
    df_results = monte_carlo_experiment(
        config_before,
        config_after,
        replications=REPLICATIONS,
        sim_time=SIM_TIME,
        seed=RANDOM_SEED,
    )
    project_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(project_dir, 'phd_simulation_replications.csv')
    df_results.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"仿真逐次结果已保存至: {csv_path}")

    # Welch 独立样本 t 检验：两个场景未使用配对随机数。
    th_before = df_results[df_results['Scenario'].str.contains('Before')]['Throughput']
    th_after = df_results[df_results['Scenario'].str.contains('After')]['Throughput']
    
    t_stat_th, p_val_th = stats.ttest_ind(th_after, th_before, equal_var=False)

    print("\n" + "="*50)
    print("【蒙特卡洛仿真及统计学推断报告 (N=30)】")
    print("="*50)
    
    desc = df_results.groupby('Scenario')['Throughput'].describe()[['mean', 'std', 'min', 'max']]
    print(desc.to_string(float_format="{:.1f}".format))
    
    print("\n【统计学显著性检验 (T-Test)】")
    print(f"t-statistic: {t_stat_th:.4f}")
    print(f"p-value:     {p_val_th:.2e}")
    if p_val_th < 0.01:
        print("结论: 在当前参数化情景与抽样假设下，模拟产量均值存在差异；此结果不代表工厂实测效果或因果证据。")
    
    generate_academic_dashboard(df_results, t_stat_th, p_val_th)
