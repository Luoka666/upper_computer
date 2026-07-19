"""
serial_reader.py — 串口通信验证脚本
=============================
功能：打开串口 COM5，接收 STM32 下位机发来的温湿度数据并打印到控制台。
用途：在开发上位机界面前，先验证串口通信链路是否正常。

使用方式：
  1. 激活虚拟环境：source venv/Scripts/activate
  2. 运行脚本：python serial_reader.py
  3. 按 Ctrl+C 停止
"""

import serial  # pyserial 库，用于串口通信
import sys     # sys.exit() 安全退出程序
import time    # 延时用


# ======================== 串口配置 ========================
# 这些参数必须与 STM32 下位机的 USART1 配置完全一致
SERIAL_PORT = "COM5"       # 串口号（根据设备管理器中的实际端口号修改）
BAUD_RATE = 9600           # 波特率，必须与下位机一致
DATA_BITS = serial.EIGHTBITS  # 8 位数据位（默认值，一般不需要改）
PARITY = serial.PARITY_NONE   # 无校验位（默认值）
STOP_BITS = serial.STOPBITS_ONE  # 1 位停止位（默认值）
TIMEOUT = 1.0              # 读取超时（秒），避免 readline() 永久阻塞


def open_serial():
    """
    打开串口并返回串口对象。
    如果打开失败，打印具体错误信息并退出程序。
    """
    try:
        # serial.Serial() 是 pyserial 的核心函数，参数说明：
        #   port     — 串口号，Windows 下是 "COMx"
        #   baudrate — 波特率，常用值：9600, 115200 等
        #   timeout  — 读取超时（秒），超时后返回已收到的数据（可能不完整）
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUD_RATE,
            bytesize=DATA_BITS,
            parity=PARITY,
            stopbits=STOP_BITS,
            timeout=TIMEOUT,
        )
        print(f"[成功] 串口 {SERIAL_PORT} 已打开，波特率 {BAUD_RATE}")
        return ser

    except serial.SerialException as e:
        # SerialException 常见原因：
        #   1. COM 口号不存在（设备管理器里确认一下）
        #   2. 串口被其他程序占用（串口助手没关？）
        #   3. USB TO TTL 没插好
        print(f"[错误] 无法打开串口 {SERIAL_PORT}：{e}")
        print("请检查：")
        print("  1. USB TO TTL 是否已连接")
        print("  2. 设备管理器中 COM 口号是否正确")
        print("  3. 是否有其他程序（串口助手等）占用了该串口")
        sys.exit(1)  # 非零退出码表示异常退出


def read_loop(ser):
    """
    主循环：持续从串口读取数据并打印。

    ser.readline() 的行为：
      - 一直等待，直到收到换行符 \n 或超时（timeout）
      - 返回 bytes 类型，例如 b'Temp:25 Humi:39\r\n'
      - 需要用 .decode() 转为字符串，.strip() 去掉末尾的 \r\n
    """
    print("\n正在等待下位机数据... 按 Ctrl+C 停止\n")
    print("=" * 50)

    line_count = 0  # 已收到的行数计数器

    try:
        while True:
            # ① 读取一行数据（以 \n 结尾，STM32 发送的格式以 \r\n 结尾）
            raw_line = ser.readline()

            if raw_line:
                # ② bytes → 字符串：decode('utf-8') 将字节流转为 Python 字符串
                #    .strip() 去掉首尾的空白字符（包括 \r, \n, 空格）
                line = raw_line.decode("utf-8", errors="ignore").strip()

                if line:
                    line_count += 1
                    # ③ 打印到控制台
                    print(f"[{line_count:04d}] {line}")

        # 注意：超时时 readline() 返回空 bytes b''，上面的 if raw_line 会跳过，
        #       所以超时不会打印空行，循环会继续等待下一帧数据。

    except KeyboardInterrupt:
        # Ctrl+C 被按下时触发 KeyboardInterrupt 异常
        # 这是用户主动停止程序的信号，属于正常退出
        print(f"\n\n共收到 {line_count} 条数据，程序已停止。")

    except serial.SerialException as e:
        # 通信过程中串口异常断开（比如 USB 被拔出）
        print(f"\n[错误] 串口通信异常：{e}")


def main():
    """
    主函数：串联"打开串口 → 读取数据 → 关闭串口"的完整流程。
    """
    print("=" * 50)
    print("  STM32 温湿度监测系统 — 串口通信验证")
    print("=" * 50)

    ser = open_serial()  # ① 打开串口

    try:
        read_loop(ser)    # ② 进入读取循环
    finally:
        # ③ finally 保证无论如何都会关闭串口
        #    即使是异常退出也会执行，避免串口被"锁死"
        ser.close()
        print(f"串口 {SERIAL_PORT} 已关闭。")


# ======================== 程序入口 ========================
if __name__ == "__main__":
    main()
