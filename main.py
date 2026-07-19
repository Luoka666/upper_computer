"""
main.py — STM32 温湿度上位机（核心程序）
=========================================
功能：
  1. 通过串口 COM5（9600bps）接收 STM32 下位机发来的温湿度数据
  2. 正则解析 "Temp:xx Humi:xx" 格式的 ASCII 数据
  3. 用 matplotlib.animation 实时绘制双 Y 轴动态曲线
     - 左 Y 轴（红色）：温度 0~50°C
     - 右 Y 轴（蓝色）：湿度 0~100%

使用方式：
  venv/Scripts/python.exe main.py
  关闭图表窗口即可退出。

依赖：pyserial, matplotlib（以及自动安装的 numpy）
"""

import serial
import re
import sys
import time                      # 用于断线重连的时间戳判断

# matplotlib 相关
import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["SimHei"]   # 指定默认字体为黑体（Windows 自带）
matplotlib.rcParams["axes.unicode_minus"] = False     # 解决负号 "-" 显示为方块的问题
import matplotlib.pyplot as plt
import matplotlib.animation as animation


# ======================== 配置常量 ========================
# 串口配置（必须与 STM32 下位机一致）
SERIAL_PORT = "COM5"
BAUD_RATE = 9600
SERIAL_TIMEOUT = 0.1   # 串口读取超时（秒），设小一点，利于非阻塞轮询

# 数据缓冲区配置
MAX_POINTS = 50        # X 轴最多显示 50 个数据点

# 图表刷新间隔（毫秒）
# 下位机每 100ms 发一帧，这里也设 100ms，基本同步
REFRESH_INTERVAL = 100

# Y 轴范围
TEMP_Y_MIN, TEMP_Y_MAX = 0, 50     # 温度轴范围（°C）
HUMI_Y_MIN, HUMI_Y_MAX = 0, 100    # 湿度轴范围（%）

# 断线重连配置
RECONNECT_INTERVAL = 2.0  # 断线后每隔 2 秒尝试重连一次


# ======================== 全局状态 ========================
"""
这里使用模块级全局变量来共享状态。
对于这种小工具程序，全局变量是最简单直接的做法，
不必引入 class 增加复杂度。等你以后扩展功能时，
可以考虑封装成类。
"""

# 数据缓冲区：使用普通 list 存储全部历史数据，不丢弃旧值
# 用户可用 matplotlib 工具栏（缩放 🔍 / 平移 ✋）回溯任意时间段的数据
temp_buffer = []
humi_buffer = []
x_data = []                            # X 轴序号，与数据一一对应

frame_counter = 0   # 总帧计数器，也用作 X 轴坐标

# 连接状态管理
CONN_CONNECTED = "connected"        # 串口正常连接中
CONN_DISCONNECTED = "disconnected"  # 串口已断开
conn_state = CONN_CONNECTED         # 当前连接状态
last_reconnect_time = 0             # 上次尝试重连的时间戳（用 time.time()）
status_text_obj = None              # 图表上的状态文字 Artist 对象（setup_plot 中初始化）
ser = None                           # 全局串口对象（重连时会重新赋值）


# ======================== 串口模块 ========================

def open_serial(exit_on_fail=True):
    """
    打开串口 COM5。

    参数：
        exit_on_fail : bool — True=失败时退出程序（首次启动用）
                             False=失败时返回 None（断线重连用）

    返回：
        成功返回 Serial 对象，失败时根据 exit_on_fail 决定行为。
    """
    try:
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUD_RATE,
            timeout=SERIAL_TIMEOUT,
        )
        return ser
    except serial.SerialException as e:
        if exit_on_fail:
            print(f"[错误] 无法打开串口 {SERIAL_PORT}：{e}")
            print("请检查：")
            print("  1. USB TO TTL 连接是否正常")
            print("  2. 设备管理器中 COM 口号是否为 COM5")
            print("  3. 是否有其他程序占用了该串口")
            sys.exit(1)
        else:
            # 静默失败，让调用方处理（断线重连场景）
            return None


def safe_close_serial(ser):
    """
    安全关闭串口。
    即使 ser 已经被拔线（is_open=False 或抛出异常）也不会崩溃。
    """
    if ser is None:
        return
    try:
        if ser.is_open:
            ser.close()
    except (serial.SerialException, OSError, AttributeError):
        # 串口可能已经物理断开，close() 会抛异常，忽略即可
        pass


def read_serial_nonblocking(ser):
    """
    非阻塞地读取串口缓冲区中所有可用的数据。

    工作原理（非阻塞 vs 阻塞的区别）：
      - ser.readline()       → 阻塞，没数据就一直等（会卡住动画）
      - ser.in_waiting()     → 返回缓冲区中待读取的字节数，没有就是 0
      - ser.readline()       → 在确认有数据后再调用，立刻返回，不会卡住

    由于下位机每 100ms 发一帧，而 FuncAnimation 每 100ms 调用一次，
    所以每次通常能读到 0~1 帧数据，动画不会丢帧也不会卡顿。

    注意：不再在内部捕获 SerialException，而是让它向上抛出，
         由 update() 统一处理断线重连逻辑。

    返回：
        解析到的 (temp, humi) 列表，可能为空列表。
    """
    results = []

    # 只要串口接收缓冲区里还有数据，就继续读
    # readline() 按 \n 读取一行，天然防粘包：
    # 即使缓冲区堆积多帧数据，每次也只取一帧，不会出现半帧或跨帧拼接。
    while ser.in_waiting > 0:
        raw_line = ser.readline()
        if raw_line:
            line = raw_line.decode("utf-8", errors="ignore").strip()
            if line:
                temp, humi = parse_line(line)
                if temp is not None and humi is not None:
                    results.append((temp, humi))

    return results


def parse_line(line):
    """
    从 "Temp:25 Humi:39" 中提取温度和湿度数值。

    参数：
        line : str — 一行原始字符串

    返回：
        (temp, humi) — 两个 int 值；解析失败返回 (None, None)
    """
    try:
        # r'\d+' 匹配一个或多个连续数字
        numbers = re.findall(r"\d+", line)
        if len(numbers) >= 2:
            temp = int(numbers[0])
            humi = int(numbers[1])
            return temp, humi
        return None, None
    except (ValueError, IndexError):
        return None, None


# ======================== 图表模块 ========================

def setup_plot():
    """
    初始化 matplotlib 图表：双 Y 轴、标签、图例、样式。

    返回：
        fig  — 图窗对象
        ax1  — 左 Y 轴（温度，红色）
        ax2  — 右 Y 轴（湿度，蓝色）
        line_temp — 温度曲线 Line2D 对象
        line_humi — 湿度曲线 Line2D 对象
    """
    # ① 创建图窗和主坐标轴
    fig, ax1 = plt.subplots(figsize=(10, 5))
    fig.canvas.manager.set_window_title("STM32 温湿度监测上位机")

    # ①.⑤ 关键：禁用 X 轴自动缩放。
    # 因为我们用 list 存储了全部历史数据，set_data() 传入的 X 范围
    # 会越来越大（0→300→600...），必须禁止 matplotlib 自动调整 X 轴，
    # 改为由 update() 中手动 set_xlim() 控制滚动窗口。
    ax1.set_autoscalex_on(False)
    ax1.set_xlim(0, MAX_POINTS)    # 初始显示范围：0~50

    # ② 创建副坐标轴（右 Y 轴，与 ax1 共享 X 轴）
    ax2 = ax1.twinx()

    # ③ 设置坐标轴范围和标签
    # -- 温度轴（左）--
    ax1.set_ylim(TEMP_Y_MIN, TEMP_Y_MAX)
    ax1.set_ylabel("温度 (°C)", color="red", fontsize=12)
    ax1.tick_params(axis="y", labelcolor="red")
    ax1.set_xlabel("帧序号", fontsize=12)

    # -- 湿度轴（右）--
    ax2.set_ylim(HUMI_Y_MIN, HUMI_Y_MAX)
    ax2.set_ylabel("湿度 (%)", color="blue", fontsize=12)
    ax2.tick_params(axis="y", labelcolor="blue")

    # ④ 标题和网格
    ax1.set_title("温湿度实时监测曲线", fontsize=14, fontweight="bold")
    ax1.grid(True, linestyle="--", alpha=0.4)

    # ④.⑤ 状态文字（左上角，初始为空，断线时显示提示）
    status_text = ax1.text(
        0.02, 0.98,                  # 相对坐标：左上角（2% 左边距，98% 上边距）
        "",                           # 初始空字符串，无文字
        transform=ax1.transAxes,      # 使用相对坐标系（0~1），不受数据缩放影响
        fontsize=12,
        color="orange",
        fontweight="bold",
        verticalalignment="top",
        bbox=dict(                    # 文字背景框，增加可读性
            boxstyle="round,pad=0.3",
            facecolor="black",
            edgecolor="orange",
            alpha=0.8,
        ),
    )

    # ⑤ 创建两条初始为空的曲线（数据在 update() 里动态填充）
    #    这里只创建 Line2D 对象，不设数据，后面用 .set_data() 更新
    line_temp, = ax1.plot(
        [], [],
        color="red",
        linewidth=1.5,
        marker=".",
        markersize=2,
        label="温度 (°C)",
    )

    line_humi, = ax2.plot(
        [], [],
        color="blue",
        linewidth=1.5,
        marker=".",
        markersize=2,
        label="湿度 (%)",
    )

    # ⑥ 合并图例（两条曲线属于不同坐标轴，需手动合并）
    lines = [line_temp, line_humi]
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="upper right", fontsize=10)

    # ⑦ 调整布局
    fig.tight_layout()

    return fig, ax1, ax2, line_temp, line_humi, status_text


# ======================== 动画更新回调 ========================
# 这是整个程序的心脏：
# FuncAnimation 每 100ms 调用一次这个函数，实现"实时"效果。

def create_update_func(line_temp, line_humi, ax1, status_text):
    """
    创建 update() 回调函数的工厂函数。

    参数：
        line_temp   — 温度曲线的 Line2D 对象
        line_humi   — 湿度曲线的 Line2D 对象
        ax1         — 左 Y 轴（温度）
        status_text — 图表左上角的状态文字 Text 对象
    """

    def update(frame):
        """
        每 REFRESH_INTERVAL 毫秒被 FuncAnimation 调用一次。

        做的事：
          ① 如果已连接 → 尝试读取串口数据
          ② 如果断线   → 尝试定时重连
          ③ 更新两条曲线的数据
          ④ 动态调整 X 轴范围（滚动效果）
          ⑤ 更新状态文字（断线提示 / 恢复提示）
        """
        global frame_counter, conn_state, last_reconnect_time, ser

        # ============================================================
        # 阶段一：串口读取 / 重连
        # ============================================================

        if conn_state == CONN_CONNECTED:
            # ---- 已连接状态：尝试读取数据 ----
            try:
                new_data = read_serial_nonblocking(ser)
            except (serial.SerialException, OSError, AttributeError) as e:
                # 读取时发生异常 → 串口断了！
                print(f"[断线] 串口连接丢失：{e}")
                conn_state = CONN_DISCONNECTED
                last_reconnect_time = time.time()   # 记录断线时间，开始重连倒计时
                safe_close_serial(ser)               # 安全关闭旧串口
                ser = None
                status_text.set_text("⏳ 串口断开，正在重连...")
                new_data = []
        else:
            # ---- 断线状态：尝试重连 ----
            new_data = []
            now = time.time()

            # 每隔 RECONNECT_INTERVAL 秒尝试重连一次
            if now - last_reconnect_time >= RECONNECT_INTERVAL:
                last_reconnect_time = now
                print(f"[重连] 正在尝试重新连接 {SERIAL_PORT}...")
                ser = open_serial(exit_on_fail=False)  # 静默模式，不退出

                if ser is not None:
                    # 重连成功！
                    conn_state = CONN_CONNECTED
                    status_text.set_text("")            # 清除提示文字
                    print(f"[重连] ✓ 串口 {SERIAL_PORT} 已恢复！")
                else:
                    # 重连失败，更新提示文字
                    status_text.set_text(f"⏳ 串口断开，正在重连...（{int(now)}）")

        # ============================================================
        # 阶段二：数据写入缓冲区
        # ============================================================

        for temp, humi in new_data:
            frame_counter += 1
            temp_buffer.append(temp)
            humi_buffer.append(humi)
            x_data.append(frame_counter)

        # ============================================================
        # 阶段三：更新曲线
        # ============================================================

        if len(x_data) > 0:
            # 用全部历史数据更新曲线
            line_temp.set_data(list(x_data), list(temp_buffer))
            line_humi.set_data(list(x_data), list(humi_buffer))

            # 智能 X 轴滚动：
            #   - 用户在看最新数据 → 自动跟随滚动（最近 MAX_POINTS 个点）
            #   - 用户手动拖到历史区域 → 停止自动滚动，保留用户视图
            target_right = max(frame_counter, MAX_POINTS)
            target_left = max(0, frame_counter - MAX_POINTS)

            # 判断：当前视图右边界是否接近"最新数据"的位置
            # 容差 10 帧（约 1 秒），防止微小抖动触发离开
            user_is_at_latest = ax1.get_xlim()[1] >= target_right - 10

            if user_is_at_latest:
                ax1.set_xlim(target_left, target_right)

        # 返回所有需要重绘的 Artist 对象（blit=True 时需要）
        return line_temp, line_humi, status_text

    return update


# ======================== 主程序 ========================

def main():
    """
    主函数：串联 打开串口 → 初始化图表 → 启动动画 → 显示窗口 的完整流程。
    """
    global ser  # 声明使用模块级全局 ser，这样重连时才能重新赋值

    print("=" * 55)
    print("  STM32 温湿度监测上位机 v1.1（支持断线重连）")
    print("=" * 55)
    print(f"串口：{SERIAL_PORT} @ {BAUD_RATE} bps")
    print(f"缓冲区：{MAX_POINTS} 个数据点")
    print(f"刷新率：{REFRESH_INTERVAL} ms")
    print(f"重连间隔：{RECONNECT_INTERVAL} 秒")
    print()

    # ① 打开串口（首次启动，失败则退出）
    ser = open_serial(exit_on_fail=True)

    # ② 初始化图表
    fig, ax1, ax2, line_temp, line_humi, status_text = setup_plot()
    toolbar = fig.canvas.toolbar

    def _jump_to_latest(*args, **kwargs):
        """跳到最新 50 个数据点并恢复实时滚动"""
        right = max(frame_counter, MAX_POINTS)
        left = max(0, frame_counter - MAX_POINTS)
        ax1.set_xlim(left, right)
        fig.canvas.draw()
        print("[视图] 已跳转到最新数据")

    # ②.⑤ 添加自定义按钮 "回到实时"
    #      TkAgg 后端：直接在 toolbar（Tk Frame）里加一个 ttk.Button
    import tkinter as tk
    import tkinter.ttk as ttk

    _frame = tk.Frame(toolbar)  # 用 Frame 包裹，方便控制间距
    _frame.pack(side="left", padx=(8, 0))

    _btn = ttk.Button(_frame, text="▶ 回到实时", command=_jump_to_latest)
    _btn.pack()

    # 键盘快捷键兜底：按 L 键也能跳回最新
    fig.canvas.mpl_connect("key_press_event",
        lambda e: _jump_to_latest() if e.key == "l" else None)
    print("[提示] 点击工具栏 '▶ 回到实时' 按钮 或 按 L 键 → 跳转到最新数据")

    # ③ 创建 update 回调函数
    update_func = create_update_func(line_temp, line_humi, ax1, status_text)

    # ④ 启动动画
    """
    FuncAnimation 小课堂：
      - fig：要更新的图窗
      - update_func：每 interval 毫秒调用一次的回调
      - interval：刷新间隔（毫秒），这里 100ms 与下位机帧率一致
      - cache_frame_data=False：不缓存历史帧，节省内存
      - blit=True：增量重绘（只重绘变化的部分），显著降低 CPU 占用
    """
    ani = animation.FuncAnimation(
        fig,
        update_func,
        interval=REFRESH_INTERVAL,
        cache_frame_data=False,
        blit=False,
    )

    print("图表已启动！关闭窗口即可退出。")
    print()

    # ⑤ 显示图表窗口（阻塞，直到用户关闭窗口）
    try:
        plt.show()
    except KeyboardInterrupt:
        print("\n收到 Ctrl+C，正在退出...")
    finally:
        # ⑥ 清理：安全关闭串口
        safe_close_serial(ser)
        print(f"串口 {SERIAL_PORT} 已关闭。")
        print(f"共接收 {frame_counter} 帧数据。")
        if temp_buffer:
            print(f"最终温度：{temp_buffer[-1]}°C")
            print(f"最终湿度：{humi_buffer[-1]}%")


if __name__ == "__main__":
    main()
