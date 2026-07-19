"""
plot_display.py — 静态图表测试脚本
===================================
功能：用随机生成的假数据，测试 matplotlib 双 Y 轴静态图表是否正常显示。
     温度曲线（红色，左 Y 轴），湿度曲线（蓝色，右 Y 轴）。

使用方式：
  venv\Scripts\python.exe plot_display.py
  弹出图表窗口后，关闭窗口即可退出。
"""

import random
import matplotlib.pyplot as plt   # 绘图核心库


# ======================== 假数据生成 ========================
# 模拟 50 个数据点（约 5 秒的数据，每 100ms 一帧）

DATA_COUNT = 50

def generate_fake_data():
    """
    生成模拟的温湿度数据。
    温度在 25±3°C 范围内随机波动，湿度在 40±10% 范围内随机波动。
    这模拟了实际的传感器读数，带有自然的小幅波动。
    """
    temps = []
    humis = []
    for i in range(DATA_COUNT):
        # random.randint(a, b) 生成 [a, b] 之间的随机整数
        temps.append(random.randint(23, 28))   # 温度 23~28°C
        humis.append(random.randint(35, 45))   # 湿度 35~45%
    return temps, humis


# ======================== 绘图函数 ========================
# 这段代码是后续实时曲线的核心框架，理解了这里就理解了整个画图逻辑。

def plot_static(temps, humis):
    """
    绘制双 Y 轴静态图表。

    matplotlib 双 Y 轴的核心步骤：
      ① fig, ax1 = plt.subplots()       → 创建图窗 + 主坐标轴（温度用）
      ② ax2 = ax1.twinx()               → 创建共享 X 轴的"孪生"坐标轴（湿度用）
      ③ ax1.plot(..., color='red')      → 在左 Y 轴上画温度曲线
      ④ ax2.plot(..., color='blue')     → 在右 Y 轴上画湿度曲线
      ⑤ ax1.set_ylabel(...) / ax2.set_ylabel(...) → 分别设置标签
      ⑥ 两条曲线的图例合并，放在一个位置
    """

    # --- ① 创建画布和主坐标轴 ---
    # fig：整张图的容器
    # ax1：主坐标轴（左 Y 轴），用于显示温度
    fig, ax1 = plt.subplots(figsize=(10, 5))  # figsize=(宽,高)，单位英寸
    fig.canvas.manager.set_window_title("温湿度监测 — 静态测试")

    # --- ② 创建副坐标轴 ---
    # ax1.twinx() 创建与 ax1 共享 X 轴的新坐标轴，Y 轴在右侧
    ax2 = ax1.twinx()

    # --- ③ X 轴数据 ---
    # 用 0, 1, 2, ..., 49 作为横坐标（表示帧序号或时间点）
    x = list(range(DATA_COUNT))

    # --- ④ 画温度曲线（左 Y 轴，红色） ---
    line_temp, = ax1.plot(
        x, temps,
        color="red",           # 线条颜色
        linewidth=1.5,         # 线宽
        marker=".",            # 数据点标记样式：小圆点
        markersize=3,          # 标记大小
        label="温度 (°C)",     # 图例标签
    )

    # --- ⑤ 画湿度曲线（右 Y 轴，蓝色） ---
    line_humi, = ax2.plot(
        x, humis,
        color="blue",
        linewidth=1.5,
        marker=".",
        markersize=3,
        label="湿度 (%)",
    )

    # --- ⑥ 设置坐标轴范围和标签 ---
    # 温度轴（左 Y 轴）
    ax1.set_ylim(0, 50)          # Y 轴范围 0~50°C（比你要求的多留一点余量）
    ax1.set_ylabel("温度 (°C)", color="red", fontsize=12)
    ax1.tick_params(axis="y", labelcolor="red")  # Y 轴刻度数字也用红色
    ax1.set_xlabel("帧序号", fontsize=12)

    # 湿度轴（右 Y 轴）
    ax2.set_ylim(0, 100)         # Y 轴范围 0~100%
    ax2.set_ylabel("湿度 (%)", color="blue", fontsize=12)
    ax2.tick_params(axis="y", labelcolor="blue")  # Y 轴刻度数字也用蓝色

    # --- ⑦ 设置标题 ---
    ax1.set_title("温湿度监测曲线（静态测试）", fontsize=14, fontweight="bold")

    # --- ⑧ 合并图例 ---
    # 两条曲线分属不同坐标轴，需要手动合并图例
    lines = [line_temp, line_humi]
    labels = [line.get_label() for line in lines]
    ax1.legend(lines, labels, loc="upper right", fontsize=10)

    # --- ⑨ 启用网格 ---
    ax1.grid(True, linestyle="--", alpha=0.5)  # 虚线半透明网格，方便读数

    # --- ⑩ 调整布局并显示 ---
    fig.tight_layout()  # 自动调整边距，防止标签被截断
    print("图表已生成，关闭窗口即可退出。")
    plt.show()          # 阻塞，直到用户关闭窗口


def main():
    print("=" * 50)
    print("  STM32 温湿度监测系统 — 静态图表测试")
    print("=" * 50)

    # ① 生成假数据
    temps, humis = generate_fake_data()
    print(f"已生成 {DATA_COUNT} 组模拟数据")
    print(f"温度范围：{min(temps)}~{max(temps)}°C")
    print(f"湿度范围：{min(humis)}~{max(humis)}%")

    # ② 绘图
    plot_static(temps, humis)


if __name__ == "__main__":
    main()
