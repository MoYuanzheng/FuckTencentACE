import psutil
import time
import sys
import ctypes
import ctypes.wintypes as wintypes
import threading
import os
from pathlib import Path
from tkinter import Tk, Text, Scrollbar, Frame, Button, Label, END, DISABLED, NORMAL
from tkinter import font as tkfont
from typing import List
from PIL import Image
import pystray
from pystray import MenuItem as item

# 配置参数
TARGET_PROCESSES = ["SGuard64.exe", "SGuardSvc64.exe"]
CHECK_INTERVAL = 180  # 检查间隔（秒）
FIRST_DELAY = 180  # 首次检测延迟（秒）
TARGET_CPU = None  # 目标CPU核心（None自动选择最后一个）

# 单实例互斥量句柄（保持引用以防被GC释放）
SINGLE_INSTANCE_HANDLE = None

# 获取资源文件路径（支持打包后的路径）


def resource_path(relative_path):
    """获取资源文件的绝对路径，兼容开发环境和打包后的环境"""
    try:
        # PyInstaller创建临时文件夹,将路径存储在_MEIPASS中
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def enable_high_dpi_awareness():
    """在Windows上启用高DPI感知，避免缩放导致的模糊。"""
    if not psutil.WINDOWS:
        return
    try:
        # Windows 10 Creators Update 及以上，支持每显示器V2
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
        return
    except Exception:
        pass
    try:
        # Windows 8.1 API（系统/每显示器DPI）
        ctypes.windll.shcore.SetProcessDpiAwareness(
            2)  # PROCESS_PER_MONITOR_DPI_AWARE
        return
    except Exception:
        pass
    try:
        # Windows Vista/7 兼容API（系统DPI感知）
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def set_tk_dpi_scaling(root):
    """根据当前窗口DPI设置 Tk 的缩放比例，保证字体与控件清晰。"""
    try:
        dpi = None
        # 优先使用每窗口DPI（Win10）
        get_dpi_for_window = getattr(
            ctypes.windll.user32, 'GetDpiForWindow', None)
        if get_dpi_for_window:
            hwnd = root.winfo_id()
            dpi = int(get_dpi_for_window(hwnd))
        else:
            # 回退到设备上下文DPI
            hdc = ctypes.windll.user32.GetDC(0)
            if hdc:
                LOGPIXELSX = 88
                dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, LOGPIXELSX)
                ctypes.windll.user32.ReleaseDC(0, hdc)

        if dpi and dpi > 0:
            # Tk 的 scaling 是 每点(1/72英寸)对应的像素数
            scale = float(dpi) / 72.0
            root.tk.call('tk', 'scaling', scale)
    except Exception:
        # 忽略缩放设置失败，继续默认行为
        pass


def show_and_focus_window(hwnd: int) -> bool:
    """显示并聚焦已有窗口（若存在）。"""
    try:
        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        # 允许前台切换
        try:
            user32.AllowSetForegroundWindow(-1)
        except Exception:
            pass
        user32.ShowWindow(wintypes.HWND(hwnd), SW_RESTORE)
        user32.SetForegroundWindow(wintypes.HWND(hwnd))
        return True
    except Exception:
        return False


def focus_existing_instance_by_title(title: str) -> bool:
    """通过窗口标题定位并激活窗口。"""
    try:
        user32 = ctypes.windll.user32
        user32.FindWindowW.restype = wintypes.HWND
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            return show_and_focus_window(hwnd)
        return False
    except Exception:
        return False


def enum_windows_for_pids(target_pids) -> int:
    """遍历顶层窗口，返回第一个属于目标PID集合的窗口句柄（可能为隐藏窗口）。"""
    user32 = ctypes.windll.user32

    EnumWindows = user32.EnumWindows
    GetWindowThreadProcessId = user32.GetWindowThreadProcessId
    EnumWindows.restype = wintypes.BOOL
    EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]

    found_hwnd = wintypes.HWND(0)

    @EnumWindowsProc
    def callback(hwnd, lParam):
        nonlocal found_hwnd
        pid = wintypes.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if int(pid.value) in target_pids:
            found_hwnd = hwnd
            return False  # 停止枚举
        return True

    EnumWindows(callback, 0)
    return int(found_hwnd.value)


def focus_existing_instance() -> bool:
    """尝试激活已运行的窗口（通过标题或PID枚举）。"""
    # 先通过固定标题尝试定位
    if focus_existing_instance_by_title("FuckTencentACE  github@moyuanzheng"):
        return True

    # 通过进程名/命令行匹配，枚举窗口
    candidate_pids = set()
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = (proc.info.get('name') or '').lower()
            cmdline_list = proc.info.get('cmdline') or []
            cmdline = ' '.join(cmdline_list).lower()

            # 打包后可能为 fuckace.exe 或 fucktencentace.exe
            if name in ("fuckace.exe", "fucktencentace.exe", "fuckace"):
                candidate_pids.add(proc.info['pid'])
                continue

            # 源码运行：python* + FuckACE.py
            if ("python" in name) and ("fuckace.py" in cmdline):
                candidate_pids.add(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    if not candidate_pids:
        return False

    hwnd = enum_windows_for_pids(candidate_pids)
    if hwnd:
        return show_and_focus_window(hwnd)
    return False


def acquire_single_instance_mutex(name: str) -> bool:
    """创建命名互斥量，若已存在则返回 False。"""
    global SINGLE_INSTANCE_HANDLE
    try:
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        CreateMutexW = kernel32.CreateMutexW
        CreateMutexW.argtypes = [ctypes.c_void_p,
                                 wintypes.BOOL, wintypes.LPCWSTR]
        CreateMutexW.restype = wintypes.HANDLE

        handle = CreateMutexW(None, False, name)
        if not handle:
            return True  # 创建失败时，保守起见允许继续

        last_error = ctypes.get_last_error()
        SINGLE_INSTANCE_HANDLE = handle  # 保存句柄，防GC

        # ERROR_ALREADY_EXISTS = 183
        if last_error == 183:
            return False
        return True
    except Exception:
        return True


class ProcessMonitorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("FuckTencentACE  github@moyuanzheng")
        # 设置窗口为当前屏幕宽高的一半，并居中显示
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        win_w = screen_w // 2
        win_h = screen_h // 2
        pos_x = (screen_w - win_w) // 2
        pos_y = (screen_h - win_h) // 2
        self.root.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        self.root.resizable(True, True)

        # 设置窗口图标
        try:
            icon_path = resource_path("logo.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception as e:
            print(f"无法加载图标: {e}")

        # 设置字体
        self.font = tkfont.Font(family="Microsoft YaHei", size=10)

        # 状态变量
        self.running = True
        self.first_detection = True
        self.tray_icon = None
        self.is_hidden = False

        # 拦截窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

        # 创建界面组件
        self.create_widgets()

        # 创建系统托盘图标
        self.create_tray_icon()

        # 启动监控线程
        self.monitor_thread = threading.Thread(
            target=self.monitor_processes, daemon=True)
        self.monitor_thread.start()

    def create_widgets(self):
        # 顶部标签
        header = Label(
            self.root,
            text="FuckTencentACE - 监控进程: " + ", ".join(TARGET_PROCESSES),
            font=tkfont.Font(family="Microsoft YaHei", size=12, weight="bold")
        )
        header.pack(pady=10, fill="x", padx=10)

        # 日志区域
        log_frame = Frame(self.root)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_text = Text(log_frame, wrap="word",
                             font=self.font, state=DISABLED)
        self.log_text.pack(side="left", fill="both", expand=True)
        # 增加每行日志之间的间距
        self.log_text.tag_config('logline', spacing1=2, spacing2=2, spacing3=6)

        scrollbar = Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scrollbar.set)

        # 状态条
        self.status_var = Label(
            self.root, text="就绪 - 等待监控开始", bd=1, relief="sunken", anchor="w")
        self.status_var.pack(side="bottom", fill="x")

        # 控制按钮
        btn_frame = Frame(self.root)
        btn_frame.pack(pady=10)

        self.stop_btn = Button(
            btn_frame,
            text="停止监控",
            command=self.stop_monitoring,
            font=self.font,
            width=15,
            bg="#ff4444",
            fg="white"
        )
        self.stop_btn.pack()

    def add_log(self, message, is_success=True):
        """添加日志到文本区域"""
        time_str = time.strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{time_str}] {message}\n"

        self.log_text.config(state=NORMAL)
        self.log_text.insert(END, log_entry, ('logline',))
        self.log_text.see(END)  # 滚动到最新日志
        self.log_text.config(state=DISABLED)

        # 更新状态条
        self.status_var.config(text=message)

    def get_target_priority(self):
        """获取目标优先级"""
        if psutil.WINDOWS:
            return psutil.IDLE_PRIORITY_CLASS
        else:
            self.add_log("错误：仅支持Windows系统", False)
            self.stop_monitoring()
            return None

    def get_target_core(self):
        """获取目标CPU核心"""
        if TARGET_CPU is not None:
            return [TARGET_CPU]
        cpu_count = psutil.cpu_count(logical=True)
        return [cpu_count - 1] if cpu_count > 0 else [0]

    def adjust_process(self, proc: psutil.Process, target_pri: int, target_core: List[int]):
        """调整进程优先级和CPU亲和性"""
        try:
            # 设置优先级
            if proc.nice() != target_pri:
                proc.nice(target_pri)
                self.add_log(
                    f"已调整 {proc.name()} (PID: {proc.pid}) 优先级为 {target_pri}")

            # 设置CPU亲和性
            if proc.cpu_affinity() != target_core:
                proc.cpu_affinity(target_core)
                self.add_log(
                    f"已调整 {proc.name()} (PID: {proc.pid}) CPU亲和性为 {target_core}")

            return True
        except psutil.AccessDenied:
            self.add_log(f"权限不足，无法调整进程 {proc.name()} (PID: {proc.pid})", False)
            return False
        except psutil.NoSuchProcess:
            self.add_log(f"进程已结束: {proc.name()} (PID: {proc.pid})")
            return False
        except Exception as e:
            self.add_log(f"调整进程出错: {str(e)}", False)
            return False

    def monitor_processes(self):
        """监控并限制目标进程"""
        target_pri = self.get_target_priority()
        if target_pri is None:
            return

        target_core = self.get_target_core()

        self.add_log(f"开始监控进程: {', '.join(TARGET_PROCESSES)}")
        self.add_log(f"目标配置: 优先级={target_pri}，CPU亲和性={target_core}")
        self.add_log(f"检查间隔: {CHECK_INTERVAL}秒，首次延迟: {FIRST_DELAY}秒")

        while self.running:
            try:
                # 遍历目标进程
                for pname in TARGET_PROCESSES:
                    for proc in psutil.process_iter(['pid', 'name']):
                        try:
                            if proc.info['name'] != pname:
                                continue

                            # 检查当前状态
                            current_pri = proc.nice()
                            current_affinity = proc.cpu_affinity()
                            need_adjust = (current_pri != target_pri) or (
                                current_affinity != target_core)

                            if need_adjust:
                                self.add_log(
                                    f"需要调整: {pname} (PID: {proc.pid})")
                                self.add_log(
                                    f"  当前: 优先级={current_pri}, CPU亲和性={current_affinity}")
                                self.add_log(
                                    f"  目标: 优先级={target_pri}, CPU亲和性={target_core}")

                                # 首次检测延迟处理
                                if self.first_detection:
                                    self.add_log(
                                        f"首次检测到，{FIRST_DELAY}秒后进行限制...")
                                    # 倒计时显示
                                    for i in range(FIRST_DELAY, 0, -10):
                                        if not self.running:
                                            return
                                        self.status_var.config(
                                            text=f"首次检测到，{i}秒后进行限制...")
                                        time.sleep(10)

                                    self.first_detection = False

                                # 执行调整
                                self.adjust_process(
                                    proc, target_pri, target_core)
                                time.sleep(5)
                            else:
                                self.add_log(
                                    f"无需调整: {pname} (PID: {proc.pid})")

                        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                            self.add_log(f"跳过进程 {pname}: {str(e)}")
                        except Exception as e:
                            self.add_log(f"处理进程时出错: {str(e)}", False)

                self.add_log(f"本轮检查结束，{CHECK_INTERVAL}秒后再次检查...")

                # 等待期间更新状态
                for i in range(CHECK_INTERVAL, 0, -10):
                    if not self.running:
                        return
                    self.status_var.config(text=f"等待下次检查: {i}秒")
                    time.sleep(10)

            except Exception as e:
                self.add_log(f"监控线程出错: {str(e)}", False)
                time.sleep(10)

    def stop_monitoring(self):
        """停止监控并退出程序"""
        self.running = False
        self.add_log("正在停止监控...")
        self.status_var.config(text="已停止监控，即将退出")
        self.stop_btn.config(state=DISABLED, text="退出中...")

        # 停止托盘图标
        if self.tray_icon:
            self.tray_icon.stop()

        # 延迟关闭，确保线程结束
        self.root.after(2000, self.root.destroy)

    def create_tray_icon(self):
        """创建系统托盘图标"""
        try:
            # 优先使用ico文件，如果没有则使用png
            icon_path = resource_path("logo.ico")
            if not os.path.exists(icon_path):
                icon_path = resource_path("CounterACE_logo.png")

            if os.path.exists(icon_path):
                image = Image.open(icon_path)

                # 创建托盘菜单
                menu = pystray.Menu(
                    item('显示窗口', self.show_window, default=True),
                    item('隐藏窗口', self.minimize_to_tray),
                    item('退出程序', self.quit_app)
                )

                # 创建托盘图标
                self.tray_icon = pystray.Icon(
                    "FuckTencentACE", image, "FuckTencentACE", menu)

                # 在单独线程中运行托盘图标
                threading.Thread(target=self.tray_icon.run,
                                 daemon=True).start()
            else:
                print(f"找不到图标文件: {icon_path}")
        except Exception as e:
            print(f"创建托盘图标失败: {e}")

    def minimize_to_tray(self):
        """最小化到系统托盘"""
        self.root.withdraw()
        self.is_hidden = True
        self.add_log("程序已最小化到系统托盘")

    def show_window(self):
        """从托盘显示窗口"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.is_hidden = False

    def quit_app(self):
        """退出应用程序"""
        self.stop_monitoring()


def is_admin():
    """检查是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


if __name__ == "__main__":
    # 启用高DPI感知，避免4K/高分屏模糊
    enable_high_dpi_awareness()

    # 若已有实例在运行：直接激活并退出
    if psutil.WINDOWS:
        try:
            if focus_existing_instance():
                sys.exit(0)
        except Exception:
            pass

    # 单实例互斥量：确保仅一个实例运行
    if psutil.WINDOWS:
        if not acquire_single_instance_mutex(r"Local\\FuckTencentACE_SingleInstance"):
            # 已存在实例，尽力激活其窗口
            focus_existing_instance()
            sys.exit(0)

    # 检查管理员权限
    if not is_admin():
        # 尝试以管理员权限重启
        try:
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            sys.exit(0)
        except:
            print("请以管理员权限运行程序")
            sys.exit(1)

    # 启动GUI
    root = Tk()
    # 根据当前显示器DPI调整Tk缩放，保证清晰显示
    set_tk_dpi_scaling(root)
    # 确保中文显示正常
    root.option_add("*Font", "{Microsoft YaHei} 10")
    app = ProcessMonitorGUI(root)
    root.mainloop()
