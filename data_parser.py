"""
data_parser.py — 数据解析与缓存脚本
===================================
功能：从串口接收 STM32 发来的温湿度数据，用正则提取数值，
      并存入固定长度的 deque 缓冲区，为后续画图做准备。

数据格式：Temp:25 Humi:39\r\n
提取结果：温度=25, 湿度=39

使用方式：
  1. 激活虚拟环境：venv\Scripts\activate.bat（CMD）或 source venv/Scripts/activate（Git Bash）
  2. 运行脚本：python data_parser.py
  3. 按 Ctrl+C 停止
"""

import serial
import re                          # 正则表达式库，用于从字符串中提取数字
from collections import deque      # 双端队列，支持自动丢弃旧数据的定长队列
import sys


# ======================== 串口配置 ========================
SERIAL_PORT = "COM5"
BAUD_RATE = 9600
TIMEOUT = 0.5  # 读取超时（秒），设短一些让循环响应更快


# ======================== 数据缓冲区配置 ========================
MAX_POINTS = 50  # 缓冲区大小：只保留最近 50 个数据点（约 5 秒的数据，100ms/帧）

"""
deque 小课堂：
  - deque 全称 "double-ended queue"（双端队列）
  - 设置 maxlen=50 后，当队列满了，新追加的数据会自动把最旧的数据"挤出去"
  - 省去了手动判断长度、删除旧数据的麻烦
  - 用法和 list 几乎一样：.append() 添加，直接用下标访问 [0]、[-1]
"""
temp_buffer = deque(maxlen=MAX_POINTS)   # 温度缓冲区（存储 int 值）
humi_buffer = deque(maxlen=MAX_POINTS)   # 湿度缓冲区（存储 int 值）


def open_serial():
    """打开串口 COM5，失败时打印提示并退出。"""
    try:
        ser = serial.Serial(port=SERIAL_PORT, baudrate=BAUD_RATE, timeout=TIMEOUT)
        print(f"[成功] 串口 {SERIAL_PORT} 已打开，波特率 {BAUD_RATE}")
        return ser
    except serial.SerialException as e:
        print(f"[错误] 无法打开串口 {SERIAL_PORT}：{e}")
        print("请检查 USB TO TTL 连接和 COM 口号")
        sys.exit(1)


def parse_line(line):
    """
    解析一行串口数据，提取温度和湿度数值。

    参数：
        line : str — 原始字符串，例如 "Temp:25 Humi:39"

    返回：
        (temp, humi) : (int, int) — 温度和湿度值
        如果解析失败，返回 (None, None)

    正则表达式讲解：
        r'\d+'  → 匹配一个或多个连续数字
        re.findall(r'\d+', "Temp:25 Humi:39")  →  ['25', '39']
        然后转为 int

    为什么不用 split()？
        split(':') 等方法强依赖固定格式，一旦下位机改格式就崩溃。
        正则提取数字的方式更鲁棒，只要字符串中有两个数字就行。
    """
    try:
        # 用正则提取字符串中所有的数字
        numbers = re.findall(r"\d+", line)

        if len(numbers) >= 2:
            # 取前两个数字：第一个是温度，第二个是湿度
            temp = int(numbers[0])
            humi = int(numbers[1])

            # 基本范围校验：温度 0~50°C，湿度 0~100%
            # 超出范围可能是数据损坏，打印警告但不丢弃
            if not (0 <= temp <= 60):
                print(f"  [警告] 温度值异常：{temp}°C（正常范围 0~50）")
            if not (0 <= humi <= 100):
                print(f"  [警告] 湿度值异常：{humi}%（正常范围 0~100）")

            return temp, humi
        else:
            # 数字不足 2 个，说明格式不对
            print(f"  [警告] 数据格式异常，提取到 {len(numbers)} 个数字：{line}")
            return None, None

    except ValueError as e:
        # int() 转换失败（不太可能发生，但以防万一）
        print(f"  [错误] 数值转换失败：{e}，原始数据：{line}")
        return None, None


def print_status():
    """
    打印当前缓冲区状态，包括最近的 3 个数据点。
    """
    if len(temp_buffer) == 0:
        return

    # 取最近的 3 个点（如果不足 3 个就取全部）
    recent_count = min(3, len(temp_buffer))
    recent_temps = list(temp_buffer)[-recent_count:]
    recent_humis = list(humi_buffer)[-recent_count:]

    print(f"  缓冲区：{len(temp_buffer)}/{MAX_POINTS} 个点 ", end="")
    print(f"| 最近 {recent_count} 条：", end="")
    for t, h in zip(recent_temps, recent_humis):
        print(f"[T:{t}°C H:{h}%]", end=" ")
    print()


def read_and_parse_loop(ser):
    """
    主循环：
      ① 从串口读取一行数据
      ② 解析温度和湿度
      ③ 存入 deque 缓冲区
      ④ 打印解析结果
    """
    print("\n正在接收并解析数据... 按 Ctrl+C 停止\n")
    print("=" * 55)

    line_count = 0        # 总帧数
    parse_ok_count = 0    # 成功解析帧数
    parse_fail_count = 0  # 解析失败帧数

    try:
        while True:
            raw_line = ser.readline()

            if raw_line:
                line = raw_line.decode("utf-8", errors="ignore").strip()

                if line:
                    line_count += 1
                    temp, humi = parse_line(line)

                    if temp is not None and humi is not None:
                        # 解析成功 → 存入缓冲区
                        temp_buffer.append(temp)
                        humi_buffer.append(humi)
                        parse_ok_count += 1

                        # 每 10 帧打印一次详情，其余帧只更新计数
                        # 避免打印太快看不清
                        if line_count % 10 == 0:
                            print(f"[{line_count:04d}] 温度={temp:2d}°C  湿度={humi:2d}%", end="")
                            print_status()
                    else:
                        # 解析失败 → 跳过，不存入缓冲区
                        parse_fail_count += 1

    except KeyboardInterrupt:
        print(f"\n{'=' * 55}")
        print(f"总帧数：{line_count}")
        print(f"成功：{parse_ok_count}  失败：{parse_fail_count}")
        print(f"缓冲区最终 {len(temp_buffer)} 个数据点")
        print(f"当前温度：{temp_buffer[-1] if temp_buffer else 'N/A'}°C")
        print(f"当前湿度：{humi_buffer[-1] if humi_buffer else 'N/A'}%")


def main():
    print("=" * 55)
    print("  STM32 温湿度监测系统 — 数据解析与缓存验证")
    print("=" * 55)
    print(f"缓冲区容量：{MAX_POINTS} 个数据点")
    print(f"数据格式：Temp:<温度> Humi:<湿度>\\r\\n")

    ser = open_serial()

    try:
        read_and_parse_loop(ser)
    finally:
        ser.close()
        print(f"串口 {SERIAL_PORT} 已关闭。")


if __name__ == "__main__":
    main()
