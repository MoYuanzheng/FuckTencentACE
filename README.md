## FuckTencentACE

感谢原作者@mrzhangeh
原项目链接：https://github.com/mrzhangeh/AceProcessMonitor

一个在 Windows 上运行的轻量工具，用于监控并限制腾讯 ACE 相关进程（默认：`SGuard64.exe`、`SGuardSvc64.exe`）的 CPU 优先级与 CPU 亲和性，最大限度降低其对游戏/系统性能的影响。

应用基于 Tkinter 提供可视化界面，支持系统托盘、单实例运行、自动管理员提权与高 DPI 适配。程序只做“调度属性调整”（优先级与亲和性），不注入、不修改文件。

---

### 功能特性
- **进程限制**：将目标进程优先级设为 `IDLE`，并将 CPU 亲和性固定到最后一个逻辑核心（默认策略，可配置）。
- **可视化界面**：图形化日志、状态栏、操作按钮（停止监控）。
- **系统托盘**：支持最小化到托盘；托盘菜单包含“显示窗口 / 隐藏窗口 / 退出程序”。
- **单实例运行**：自动检测已在运行的实例，若存在将激活其窗口并退出新实例。
- **管理员提权**：未以管理员权限运行时，会弹出 UAC 申请提权（需要管理员同意）。
- **高 DPI 适配**：在高分屏下保持界面清晰。

---

### 环境要求
- 操作系统：Windows 10/11 x64
- 权限：需要管理员权限（调整其他进程优先级/亲和性）
- 运行方式：
  - 发布版（推荐）：直接运行打包的 `FuckTencentACE.exe`
  - 源码运行：Python 3.8+，并安装依赖

---

### 快速开始

#### 方式一：直接运行发布版（推荐）
1. 打开 `ACE/dist/FuckTencentACE.exe`（建议右键“以管理员身份运行”）。
2. 首次运行会显示主界面，随后可关闭到托盘；托盘右键菜单可“显示/隐藏/退出”。

> 注：某些 PyInstaller 版本会在 `dist` 目录同时生成 `FuckTencentACE.pkg`。若运行时报“无法打开 pyinstaller archive”，请确保该 `.pkg` 与 `.exe` 位于同一目录（本仓库的 `build.bat` 已自动复制处理）。

#### 方式二：源码运行

在管理员 PowerShell 或 CMD 中执行：

```bat
cd ACE
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python FuckTencentACE.py
```

或在已打开的管理员 PowerShell 中：

```powershell
Start-Process python -ArgumentList 'FuckTencentACE.py' -Verb runAs
```

---

### 构建（打包为单文件 EXE）

在 `ACE` 目录下运行：

```bat
build.bat
```

成功后输出位于：`ACE/dist/FuckTencentACE.exe`（以及可能存在的 `FuckTencentACE.pkg`）。

`build.bat` 会自动：
- 升级 `pip`，安装/校验 `PyInstaller`
- 安装运行依赖（见 `requirements.txt`）
- 使用 `--onefile --windowed` 打包，并在需要时将 `FuckTencentACE.pkg` 复制到 `dist`

---

### 配置项（源码内可修改）
打开 `ACE/FuckTencentACE.py` 顶部配置：

- `TARGET_PROCESSES`：目标进程名称列表，默认 `['SGuard64.exe', 'SGuardSvc64.exe']`
- `CHECK_INTERVAL`：每轮检查间隔（秒），默认 `180`
- `FIRST_DELAY`：首次检测到目标后延迟执行（秒），默认 `180`
- `TARGET_CPU`：目标 CPU 核心索引；`None` 表示自动选择“最后一个逻辑核心”

程序默认将目标进程优先级设为 `psutil.IDLE_PRIORITY_CLASS`，并将 CPU 亲和性绑定到单个核心以降低抢占。

---

### 使用说明
- 启动后界面会显示当前监控目标、检查间隔与执行日志。
- 首次检测到目标进程时，按 `FIRST_DELAY` 倒计时后再执行限制（界面会提示进度）。
- 每轮检查结束后会等待 `CHECK_INTERVAL` 秒再次检查。
- 关闭窗口不会直接退出，而是最小化到托盘；可在托盘菜单中退出。
- 按下“停止监控”按钮将安全结束监控并退出程序。

---

### 常见问题（FAQ）
- 运行后没有界面？
  - 程序可能最小化在托盘，查看任务栏托盘区域图标；或通过托盘菜单“显示窗口”。
- 日志提示“权限不足，无法调整进程”？
  - 请以管理员身份运行程序。
- 杀软/防护软件报毒？
  - PyInstaller 打包的可执行文件有时会被误报，请自行添加信任或使用源码运行方式。
- 高分屏下界面模糊？
  - 程序已启用高 DPI 感知；若仍模糊，可在系统显示设置中检查缩放与兼容性设置。
- `FuckTencentACE.pkg` 是否必需？
  - 新版 PyInstaller 通常无需；若出现“无法打开 pyinstaller archive”，请确保 `.pkg` 与 `.exe` 同目录。`build.bat` 已处理自动复制。

---



