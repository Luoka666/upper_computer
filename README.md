# STM32 温湿度监测系统 — Python 上位机

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)]()

基于 **Python + PySerial + Matplotlib** 开发的串口数据实时可视化工具。接收 STM32 下位机通过 USART 发送的温湿度数据，在 PC 端绘制双 Y 轴动态曲线，实现 **"传感采集 -> 数据传输 -> PC 可视化"** 的完整物联网数据链路。

> 本项目是 [智能温湿度监测与报警系统](https://github.com/Luoka666/STM32F103_Loka_Project/tree/main/Temperature_Humidity_Sensor_Alarm_System) 的配套上位机。下位机基于 **STM32F103C8T6 + DHT11 温湿度传感器 + 蜂鸣器 + 0.96寸 OLED**，实现传感器驱动、阈值报警与本地显示。

---

## 项目预览

程序启动后弹出 matplotlib 图表窗口，窗口标题为"STM32 温湿度监测上位机"。图表区域包含：

- **双 Y 轴曲线**：左轴为温度（红色，0~50°C），右轴为湿度（蓝色，0~100%），X 轴为帧序号
- **状态提示**：左上角显示连接状态，正常时隐藏，断线时显示"串口断开，正在重连..."
- **工具栏**：matplotlib 原生缩放/平移按钮 + 自定义"回到实时"按钮（或按 L 键），支持从历史视图一键跳回最新数据
- **交互方式**：鼠标滚轮缩放、按住左键平移，可自由浏览任意时段的历史曲线

---

## 系统架构

整个系统分为**下位机**和**上位机**两部分，通过 USB-TTL 串口（9600bps）单向传输数据：

### 下位机端（STM32）

| 硬件模块 | 功能 | 说明 |
|----------|------|------|
| STM32F103C8T6 | 主控 MCU | 运行传感器驱动、数据处理与串口发送逻辑 |
| DHT11 | 温湿度传感器 | 单总线数字传感器，温度精度 ±2°C，湿度精度 ±5% RH |
| 蜂鸣器 | 超阈值报警 | 温度或湿度超出设定阈值时触发声光报警 |
| 0.96 寸 OLED | 本地显示 | 实时显示当前温湿度数值与系统状态 |

下位机每 100ms 采集一次传感器数据，通过 USART1 以 ASCII 文本格式发送至 PC。

### 上位机端（Python）

数据处理分为三个阶段，对应项目中的三个核心模块：

| 阶段 | 对应文件 | 职责 | 数据流向 |
|------|----------|------|----------|
| 1. 串口读取 | `serial_reader.py` -> `main.py` | 非阻塞轮询串口缓冲区，按行读取原始帧 | 字节流 -> 字符串 `"Temp:25 Humi:39"` |
| 2. 协议解析 | `data_parser.py` -> `main.py` | 正则提取温湿度数值，范围校验，写入全量缓冲区 | 字符串 -> 结构化数据 `(25, 39)` |
| 3. 图表渲染 | `plot_display.py` -> `main.py` | `FuncAnimation` 每 100ms 更新双 Y 轴曲线，智能管理视图滚动 | 数值数组 -> 可视化曲线 |

### 关键数据流

```
DHT11 传感器 -> STM32 采集 -> USART1 TX 发送 "Temp:25 Humi:39\r\n"
    -> USB-TTL 转串口 -> PC COM5 -> PySerial 非阻塞读取
    -> 正则解析 -> 全量缓冲区 -> Matplotlib FuncAnimation -> 双 Y 轴实时曲线
```

---

## 功能特性

### 核心功能

| 模块 | 功能 | 实现方式 |
|------|------|----------|
| 串口通信 | STM32 通过 USB-TTL 向 PC 单向发送数据 | PySerial，9600 bps |
| 协议解析 | 自定义 ASCII 文本协议，正则表达式精准提取数值 | `re.findall(r"\d+", line)` |
| 实时曲线 | 双 Y 轴动态曲线（温度红色、湿度蓝色），100ms 刷新率 | Matplotlib `FuncAnimation` |
| 数据回溯 | 全量存储历史数据，支持鼠标缩放/平移查看任意时段 | `ax1.set_autoscalex_on(False)` + 手动 xlim |
| 断线重连 | 串口异常断开后自动检测并重连，不退出程序 | 状态机 + 2 秒重试间隔 |
| 数据完整性 | `readline()` 天然防粘包，保证每帧数据完整不跨帧 | 非阻塞读取 + `in_waiting` 轮询 |

### 工程亮点

- **非阻塞 I/O 设计**：`ser.in_waiting` 轮询替代阻塞式 `readline()`，动画循环不会因等待串口数据而卡顿
- **智能视图管理**：检测用户是否在查看最新数据，自动切换"跟随滚动"与"固定视图"两种模式，用户手动拖拽查看历史数据时不会被强制拉回
- **渐进式开发**：项目拆分为 4 个独立可运行的脚本（串口验证 -> 解析验证 -> 图表测试 -> 完整集成），每一步都可独立调试
- **防御式编程**：对串口断开、数据格式异常、数值越界等异常情况均有容错处理
- **中文支持**：配置 SimHei 黑体字体，图表标题、坐标轴标签完美显示中文

---

## 项目结构

```
upper_computer/
├── main.py                # 核心上位机程序（实时曲线 + 断线重连）
├── serial_reader.py       # Step 1: 串口通信验证（控制台打印原始数据）
├── data_parser.py         # Step 2: 数据解析验证（正则提取 + deque 缓冲）
├── plot_display.py        # Step 3: 静态图表测试（随机假数据验证绘图）
├── requirements.txt       # 依赖清单
└── README.md
```

### 各文件定位

| 文件 | 开发阶段 | 可独立运行 | 核心价值 |
|------|----------|------------|----------|
| `serial_reader.py` | 第一步——链路验证 | 是 | 确认 STM32 <-> PC 串口物理通信正常 |
| `data_parser.py` | 第二步——协议验证 | 是 | 确认正则解析正确 + deque 缓冲区行为符合预期 |
| `plot_display.py` | 第三步——图表验证 | 是 | 脱离硬件，用假数据验证 matplotlib 双 Y 轴效果 |
| `main.py` | 最终集成 | 是 | 前三步的总装，加入实时动画、断线重连、视图管理 |

---

## 通信协议

### 数据格式

```
Temp:<温度> Humi:<湿度>\r\n
```

### 协议说明

| 字段 | 格式 | 示例 | 说明 |
|------|------|------|------|
| 温度值 | `Temp:` 后跟 1~2 位整数 | `Temp:25` | 单位 °C，范围 0~50 |
| 湿度值 | `Humi:` 后跟 1~2 位整数 | `Humi:39` | 单位 %，范围 0~100 |
| 帧分隔 | 每帧以 `\r\n` 结尾 | — | 用于 `readline()` 按行分割 |
| 发送频率 | 100ms/帧 | — | 10 fps，与动画刷新率同步 |

### 解析逻辑

```python
# 正则提取字符串中所有连续数字，不依赖固定分隔符
numbers = re.findall(r"\d+", "Temp:25 Humi:39")  # -> ['25', '39']
temp, humi = int(numbers[0]), int(numbers[1])     # -> 25, 39
```

> **设计考量**：用正则匹配数字而非 `split(':')` 硬解析，即使下位机微调格式（如加空格、改字段顺序），上位机仍可正确提取。

---

## 快速开始

### 环境要求

- Python 3.8+
- Windows 10/11（matplotlib 后端使用 TkAgg）
- STM32 下位机通过 USB-TTL 模块连接至 PC

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/Luoka666/upper_computer.git
cd upper_computer

# 2. 创建虚拟环境（推荐）
python -m venv venv
venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt
```

### 运行

```bash
# 1. 确认下位机已连接，设备管理器中查看串口号（如 COM5）

# 2. 按需修改 main.py 中的 SERIAL_PORT 为实际串口号

# 3. 启动上位机
python main.py
```

### 分步验证（推荐新手）

```bash
# Step 1: 验证串口链路
python serial_reader.py          # 应看到 "Temp:xx Humi:xx" 持续打印

# Step 2: 验证数据解析
python data_parser.py            # 应看到解析后的温湿度数值 + 缓冲区状态

# Step 3: 验证绘图（不需要硬件）
python plot_display.py           # 应看到静态双 Y 轴曲线

# Step 4: 完整运行
python main.py                   # 实时动态曲线 + 断线重连
```

---

## 断线重连机制

```
                读取异常 / 串口断开
     ┌──────────┐                ┌──────────────┐
     │ CONNECTED │ ────────────> │ DISCONNECTED │
     │  正常通信  │ <──────────── │   等待重连    │
     └──────────┘   重连成功      └──────┬───────┘
          │                             │
          │ 正常读取                     │ 每 2 秒尝试
          v                             v
    read_serial_         open_serial(exit_on_fail=False)
    nonblocking()            静默模式，失败返回 None
```

**关键设计**：
- 重连期间**程序不退出**，图表窗口保持打开
- 串口恢复后自动清除断线提示，继续接收数据
- `exit_on_fail` 参数区分首次启动（失败退出）和重连（静默失败）

---

## 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.8+ | 主语言 |
| PySerial | 3.5+ | 串口通信 |
| Matplotlib | 3.8+ | 数据可视化（TkAgg 后端） |
| NumPy | (matplotlib 依赖) | 数值计算 |
| re (标准库) | — | 正则协议解析 |
| deque (标准库) | — | 定长数据缓冲区 |

---

## 开发日志

| 阶段 | 内容 | 文件 |
|------|------|------|
| 1 | 串口链路验证——确认 STM32 数据能被 PC 正确接收 | `serial_reader.py` |
| 2 | 数据解析与缓冲——正则提取数值 + deque 定长队列 | `data_parser.py` |
| 3 | 静态图表测试——脱离硬件，用假数据验证双 Y 轴效果 | `plot_display.py` |
| 4 | 实时动画——`FuncAnimation` 驱动，100ms/帧与下位机同步 | `main.py` v0.1 |
| 5 | 断线重连——状态机实现，用户拔插 USB 无需重启程序 | `main.py` v1.0 |
| 6 | 数据回溯——全量存储 + 智能视图管理，支持查看历史趋势 | `main.py` v1.1 |

---

## 未来扩展

- [ ] 数据导出为 CSV/Excel
- [ ] 温湿度超阈值桌面通知
- [ ] 多路传感器支持（扩展协议字段）
- [ ] WebSocket 转发，实现网页端远程监控
- [ ] 打包为独立 .exe（PyInstaller）
- [ ] 多平台支持（Linux/macOS 下 matplotlib 后端自动适配）

---

## 相关项目

- [STM32F103_Loka_Project — 智能温湿度监测与报警系统](https://github.com/Luoka666/STM32F103_Loka_Project)（下位机端）
- [Luoka666 的其他项目](https://github.com/Luoka666)

---

## License

MIT License

---

<p align="center">
  <sub>Made by <a href="https://github.com/Luoka666">Luoka666</a></sub>
</p>
