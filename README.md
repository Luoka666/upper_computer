# STM32 温湿度监测系统 · Python 串口上位机

使用 **Python、PySerial、Matplotlib** 接收 STM32 串口数据并绘制温湿度曲线，是温湿度监测与报警系统的 PC 端配套工具。

**下位机入口：** [裸机版](https://github.com/Luoka666/STM32F103_Loka_Project/tree/main/Temperature_Humidity_Sensor_Alarm_System_BareMetal) · [FreeRTOS 版](https://github.com/Luoka666/STM32F103_Loka_Project/tree/main/Temperature_Humidity_Sensor_Alarm_System_FreeRTOS)

## 已实现的功能

- **双 Y 轴曲线**：温度用红色、湿度用蓝色显示；X 轴为接收样本序号，不是实际时间。
- **实时刷新**：图表目标刷新间隔为 100ms；默认显示最近 50 个样本。
- **历史浏览**：本次运行的数据保存在内存列表中，可通过 Matplotlib 工具栏缩放、平移查看。
- **回到实时**：点击工具栏“回到实时”按钮，或按 `L`，跳到最新数据并恢复跟随。
- **断线重连**：运行中读取异常后显示提示，每隔约 2 秒尝试重新打开原串口。

> 图表刷新与传感器采样是两件事：配套下位机在 RUN 连续运行期间每 2 秒尝试采样，成功后上传；100ms 是上位机检查数据和刷新图表的目标间隔。没有新样本时，不会生成新的测量值。

## 数据链路

```text
DHT11 → STM32 采集 → USART1 → USB-TTL → PySerial
      → 文本解析 → 内存历史列表 → Matplotlib 双 Y 轴曲线
```

## 快速运行

### 环境与安装

主要使用 Windows 10/11。需要 Python 3.9+、Tk 图形界面支持以及 [requirements.txt](requirements.txt) 中的依赖。Python 下限依据 [Matplotlib 3.8 的依赖要求](https://pypi.org/project/matplotlib/3.8.0/)，安装时仍需选择与 Python 版本兼容的依赖版本。主程序的自定义按钮依赖 Tk 工具栏，运行时应使用 TkAgg 后端。

```powershell
git clone https://github.com/Luoka666/upper_computer.git
cd upper_computer
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

如果 PowerShell 不允许激活虚拟环境，可以直接调用虚拟环境中的 Python：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 连接与启动

1. 完成下位机接线和烧录，使用 3.3V 电平 USB-TTL；STM32 TX 接 USB-TTL RX，两端共地。
2. 在设备管理器查看实际 COM 口，修改 [main.py](main.py) 的 `SERIAL_PORT`；串口助手和上位机不能同时占用同一个端口。
3. 下位机波特率与 `BAUD_RATE` 保持一致，当前为 **9600 bps**。
4. 指定 TkAgg 后端并启动程序；让下位机进入 RUN，等待成功采样后观察曲线。

```powershell
$env:MPLBACKEND = "TkAgg"
.\.venv\Scripts\python.exe main.py
```

关闭图表窗口即可退出，程序会释放串口。

### 配置项

| main.py 常量 | 当前设置 | 含义 |
| --- | --- | --- |
| `SERIAL_PORT` | 依环境修改 | 以本机实际 COM 口为准 |
| `BAUD_RATE` | 9600 | 与下位机保持一致 |
| `SERIAL_TIMEOUT` | 0.1 秒 | 串口读取超时 |
| `REFRESH_INTERVAL` | 100ms | 图表目标刷新间隔 |
| `MAX_POINTS` | 50 | 跟随模式的可见样本数，并非历史存储上限 |
| `RECONNECT_INTERVAL` | 2 秒 | 运行中断线后的重连尝试间隔 |

## 代码结构与阅读顺序

这些脚本是分阶段开发的独立程序，`main.py` 集成了串口、解析和绘图逻辑，并不是导入另外三个脚本运行。

| 文件 | 用途 | 是否需要硬件 |
| --- | --- | --- |
| [serial_reader.py](serial_reader.py) | 先确认串口链路，打印原始文本 | 是 |
| [data_parser.py](data_parser.py) | 验证数字解析与 deque 定长缓冲 | 是 |
| [plot_display.py](plot_display.py) | 使用模拟数据验证双 Y 轴绘图 | 否 |
| [main.py](main.py) | 集成实时曲线、历史视图和断线重连 | 是 |

各阶段脚本中的串口设置相互独立，运行前分别检查。读主程序时，推荐按 `main()` → `create_update_func()` → `read_serial_nonblocking()` / `parse_line()` → `setup_plot()` 的顺序。

## 串口协议

下位机发送 ASCII 文本，每行一组温湿度：

```text
Temp:25 Humi:39\r\n
```

温度在前，湿度在后，分别表示 °C 和 %RH。当前解析器用 `re.findall(r"\d+", line)` 提取前两个连续数字。

**当前实现边界：**

- 不支持负数或小数；不严格校验字段名、字段顺序与取值范围。不要交换温湿度顺序，也不要在前面插入其他数字。
- 先检查 `in_waiting` 再调用 `readline()`，避免无数据时主动等待；但半行数据仍可能等到 0.1 秒超时，不能保证完全非阻塞或自动保留半帧。
- 首次启动无法打开串口时会退出；自动重连针对运行中断线，并尝试原 COM 口。若重新插入后端口号改变，需要修改配置再启动。
- 历史数据只保存在本次进程内存中，尚未导出文件；长时间运行会增加内存和绘图开销。
- 视图跟随根据 X 轴右边界判断；“回到实时”可以恢复最新窗口。鼠标操作使用工具栏提供的缩放 / 平移，不承诺额外的滚轮缩放功能。

## 常见问题

| 现象 | 检查方法 |
| --- | --- |
| 无法打开串口 | 检查 COM 口、USB-TTL 驱动、线缆连接，以及是否被其他程序占用 |
| 图表没有新数据 | 确认下位机处于 RUN、波特率一致且成功输出 `Temp:… Humi:…` |
| 中文显示为方块 | 程序配置了 SimHei；确认该字体可用，或修改为本机已安装的中文字体 |
| 自定义按钮报错 | 检查 Python 的 Tk 支持与 Matplotlib TkAgg 后端 |
| 看历史时停止滚动 | 属于视图管理行为；点击“回到实时”或按 `L` 恢复 |

## 后续改进

- [ ] 接收缓冲区保留半帧，按换行符拼接完整数据。
- [ ] 按字段名严格解析，增加数值范围校验。
- [ ] 导出采样数据与时间戳。
- [ ] 限制历史缓存或分段绘制，改善长时间运行开销。

## 许可

原文声明使用 MIT License；仓库当前尚未包含独立 `LICENSE` 文件。
