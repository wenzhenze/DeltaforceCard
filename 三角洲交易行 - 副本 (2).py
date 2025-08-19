import pyautogui
import time
import cv2
import numpy as np
import threading
import keyboard
import tkinter as tk
import win32api
import win32con
import os
import pytesseract
from tkinter import ttk, scrolledtext, filedialog, messagebox
from PIL import ImageGrab



# 全局控制变量
is_running = False
is_bullet_var = False
digit_templates = {}



class AutoTraderGUI:
    def __init__(self, root):
        self.root = root
        root.title("游戏交易行监控助手 v3.2 基于b站文真则github.com/wenzhenze修改版")
        root.geometry("700x800")
        root.attributes("-topmost", True)
        self.digit_templates = {}
        self.coord_show_vars = {}  # 用于存储每个区域的显示勾选状态
        
        # 初始化OCR路径（根据实际安装位置调整）
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        
        self.default_coords = {
            '刷新按钮': (682, 209, 712, 217),
            '价格区域A': (0, 0, 0, 0),
            '价格区域B': (0, 0, 0, 0),
            '购买按钮': (1981, 1189, 2370, 1270),
            '成功提示': (1044, 198, 1510, 244),
            '失败提示': (1074, 199, 1481, 245),
            '购买数量': (2317, 1106, 2328, 1119),
            '购买数图标': (1642, 240, 1661, 259),
        }
        self.coords = self.default_coords.copy()
        self.coord_lock = threading.Lock()
        self.success_count = 0
        self.count_lock = threading.Lock()

        self.refresh_color = '#46382F'  # 默认暗金
        self.buy_icon_color = '#818689'  # 默认灰色

        self.create_coord_frame()
        self.create_config_frame()
        self.create_purchase_limit_frame()
        self.create_log_area()
        self.create_control_buttons()
        self.create_threshold_setting()
        self.create_overlay()

        keyboard.add_hotkey('F9', self.stop_monitoring)
        self.log("全局快捷键 F9 已注册")

        # 绑定事件
        for key in self.default_coords:
            for entry in self.coord_entries[key]:
                entry.bind("<KeyRelease>", lambda e, k=key: self.update_coords_and_overlay(k))

    def click(self, x, y, clicks=1):
        """使用 win32api 执行可靠的点击操作"""
        try:
            win32api.SetCursorPos((x, y))
            for _ in range(clicks):
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
                time.sleep(0.05)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)
                time.sleep(0.1)
            self.log(f"成功执行 {clicks} 次点击 ({x}, {y})")
            return True
        except Exception as e:
            self.log(f"点击失败：{str(e)}")
            return False           
    
    def perform_shutdown(self):
            try:
                self.log("将在5秒后关机...")
                os.system('shutdown /s /t 5')
            except Exception as e:
                self.log(f"关机失败: {str(e)}")
    
    def check_templates_loaded(self):
        """检查是否已加载完整的数字模板"""
        if not self.digit_templates:
            messagebox.showwarning("警告", "请先选择模板文件夹！")
            return False
        if len(self.digit_templates) < 10:
            messagebox.showwarning("警告", "模板不完整，请确保包含0-9的模板！")
            return False
        return True

    def update_coords_and_overlay(self, key):
        self.update_coords(key)  # 更新坐标字典
        self.update_overlay()   # 刷新覆盖层
    # 新增方法：更新坐标到 self.coords
    def update_coords(self, key):
        try:
            new_coords = [int(entry.get()) for entry in self.coord_entries[key]]
            self.coords[key] = tuple(new_coords)
            self.log(f"坐标 {key} 已更新为: {self.coords[key]}")  # 新增日志
        except:
            self.log(f"坐标 {key} 输入无效")

    def create_overlay(self):
        """创建透明覆盖层"""
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-transparentcolor", "gray")
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.overrideredirect(True)

        self.overlay_canvas = tk.Canvas(
            self.overlay,
            bg='gray',
            highlightthickness=0
        )
        self.overlay_canvas.pack(fill=tk.BOTH, expand=True)
        self.update_overlay()

    def update_overlay(self):
        self.overlay_canvas.delete("all")
        # 绘制所有需要显示的区域
        for key in self.coord_entries.keys():
            if self.coord_show_vars.get(key, tk.BooleanVar(value=True)).get():
                try:
                    entries = self.coord_entries[key]
                    x1 = int(entries[0].get())
                    y1 = int(entries[1].get())
                    x2 = int(entries[2].get())
                    y2 = int(entries[3].get())
                    self.overlay_canvas.create_rectangle(
                        x1, y1, x2, y2, outline='#00FF00', width=2, tags=f"region_{key}"
                    )
                except:
                    pass

    def fill_preset_coords(self, coords):
        for i, key in enumerate(["价格区域A", "价格区域B"]):
            preset_key = "A" if i == 0 else "B"
            if preset_key not in coords:
                self.log(f"预设配置错误：缺少 {preset_key} 的坐标")
                continue
            preset_values = coords[preset_key]
            if len(preset_values) != 4:
                self.log(f"预设坐标 {preset_key} 格式错误，应为4个值")
                continue
            for j in range(4):
                self.coord_entries[key][j].delete(0, tk.END)
                self.coord_entries[key][j].insert(0, str(preset_values[j]))
        
        # 关键修复：立即更新坐标字典
        self.update_coords("价格区域A")
        self.update_coords("价格区域B")
        self.update_overlay()

    def create_threshold_setting(self):
        threshold_frame = ttk.Frame(self.root)
        threshold_frame.pack(pady=5, padx=10, fill="x")

        ttk.Label(threshold_frame, text="匹配阈值（0-1）:").pack(side=tk.LEFT)
        self.threshold_entry = ttk.Entry(threshold_frame, width=5)
        self.threshold_entry.insert(0, "0.8")
        self.threshold_entry.pack(side=tk.LEFT, padx=5)

        # 热键提示
        self.hotkey_hint = ttk.Label(
            threshold_frame,
            text="停止快捷键：F9",
            foreground="gray"
        )
        self.hotkey_hint.pack(side=tk.RIGHT)

    def ocr_digit_by_template(self, region):
        best_match = -1
        best_score = -1.0  # 初始化浮点类型
        try:
            # 区域有效性检查
            if region[2] <= region[0] or region[3] <= region[1]:
                return -1

            # 截图并转换为灰度图
            img = ImageGrab.grab(bbox=region).convert("L")
            img_np = np.array(img)
            if img_np.size == 0:
                return -1

            # 模板匹配逻辑
            for digit, template in self.digit_templates.items():
                # 尺寸校验
                if template.shape[0] > img_np.shape[0] or template.shape[1] > img_np.shape[1]:
                    continue
                # 匹配计算
                res = cv2.matchTemplate(img_np, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                if max_val > best_score and max_val >= float(self.threshold_entry.get()):
                    best_score = max_val
                    best_match = digit

        except Exception as e:
            self.log(f"OCR 异常: {str(e)}")
            return -1  # 确保异常时返回默认值

        # 日志记录匹配结果
        if best_match != -1:
            self.log(f"区域 {region} 识别成功: 数字 {best_match} (置信度 {best_score:.2f})")
        else:
            self.log(f"区域 {region} 未识别到有效数字")
        return best_match
    


    def pick_region_color(self, region_key, entry_widget=None, icon_widget=None, color_attr_name=None):
        region = self.coords.get(region_key)
        if not region or region[2] <= region[0] or region[3] <= region[1]:
            self.log(f"{region_key}坐标无效，无法取色")
            return None
        img = pyautogui.screenshot(region=region).convert("RGB")
        cx = (region[2] - region[0]) // 2
        cy = (region[3] - region[1]) // 2
        rgb = img.getpixel((cx, cy))
        color_hex = '#%02X%02X%02X' % rgb

        # 如果有控件则更新界面
        if entry_widget is not None:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, color_hex)
        if icon_widget is not None:
            icon_widget.config(bg=color_hex)
        if color_attr_name is not None:
            setattr(self, color_attr_name, color_hex)

        self.log(f"{region_key}已取色: {color_hex} (位置: {region[0] + cx}, {region[1] + cy})")
        return color_hex



    def create_coord_frame(self):
        frame = ttk.LabelFrame(self.root, text="坐标设置 (格式: X1,Y1,X2,Y2)")
        frame.pack(pady=10, padx=5, fill="x")

        # 主勾选框变量
        self.master_show_var = tk.BooleanVar(value=True)

        # 主勾选框回调
        def on_master_toggle():
            val = self.master_show_var.get()
            for var in self.coord_show_vars.values():
                var.set(val)
            self.update_overlay()

        # 主勾选框控件
        master_cb = ttk.Checkbutton(
            frame,
            text="全部显示",
            variable=self.master_show_var,
            command=on_master_toggle
        )

        # 左侧：坐标输入区
        coord_frame = ttk.Frame(frame)
        coord_frame.pack(side=tk.LEFT, fill="x", expand=True)

        self.coord_entries = {}

        def on_child_toggle():
            # 检查所有子勾选框状态，更新主勾选框
            values = [var.get() for var in self.coord_show_vars.values()]
            if all(values):
                self.master_show_var.set(True)
            elif not any(values):
                self.master_show_var.set(False)
            else:
                # 部分选，设置为"不确定"状态（ttk.Checkbutton不支持三态，视觉上为未选）
                self.master_show_var.set(False)
            self.update_overlay()

        for key in self.default_coords:
            row = ttk.Frame(coord_frame)
            row.pack(fill="x", pady=2)

            show_var = tk.BooleanVar(value=True)
            self.coord_show_vars[key] = show_var

            label = tk.Label(row, text=key, width=10, anchor="w")
            label.pack(side=tk.LEFT)

            def toggle(var=show_var):
                var.set(not var.get())
                on_child_toggle()

            label.bind("<Button-1>", lambda e, var=show_var: toggle(var))

            ttk.Checkbutton(
                row,
                variable=show_var,
                command=on_child_toggle,
                takefocus=0
            ).pack(side=tk.LEFT, padx=2)

            entries = []
            for i in range(4):
                entry = ttk.Entry(row, width=5)
                entry.pack(side=tk.LEFT, padx=2)
                entry.insert(0, str(self.default_coords[key][i]))
                entries.append(entry)

            self.coord_entries[key] = entries

        # 右侧：预设按钮区
        preset_frame = ttk.Frame(frame)
        preset_frame.pack(side=tk.TOP, fill="x", padx=5)

        presets = {
            "七位数": {
                "A": (233, 1247, 248, 1270),
                "B": (253, 1247, 270, 1270)
            },
            "六位数": {
                "A": (243, 1247, 260, 1269),
                "B": (258, 1249, 273, 1269)
            },
            "四位数": {
                "A": (257, 1246, 273, 1270),
                "B": (278, 1246, 294, 1270)
            },
            "三位数": {
                "A": (267, 1247, 283, 1270),
                "B": (283, 1247, 297, 1270) 
            }
        }

        ttk.Label(preset_frame, text="快速预设:").pack(side=tk.LEFT,pady=2)
        for name, coords in presets.items():
            btn = ttk.Button(preset_frame, text=name,
                            command=lambda c=coords: self.fill_preset_coords(c))
            btn.pack(side=tk.LEFT, pady=2)



        # 取色项配置列表
        color_items = [
            {
                "label": "刷新按钮取色值:",
                "region_key": "刷新按钮",
                "color_attr": "refresh_color",
                "default": self.refresh_color,
                "icon_attr": "color_icon",
                "entry_attr": "refresh_color_entry"
            },
            {
                "label": "购买数图标取色值:",
                "region_key": "购买数图标",
                "color_attr": "icon_color",
                "default": self.buy_icon_color,
                "icon_attr": "icon_color_icon",
                "entry_attr": "icon_color_entry"
            }
        ]

        for item in color_items:
            frame_color = ttk.Frame(frame)  # 每次循环新建一个Frame
            frame_color.pack(side=tk.TOP, fill="x", padx=5, pady=2)
            ttk.Label(frame_color, text=item["label"], width=14).pack(side=tk.LEFT)
    
            icon = tk.Label(frame_color, width=2, height=1, bg=item["default"], relief="solid", borderwidth=1)
            icon.pack(side=tk.LEFT, padx=(0, 2))
            setattr(self, item["icon_attr"], icon)

            entry = ttk.Entry(frame_color, width=10)
            entry.pack(side=tk.LEFT, padx=2)
            entry.insert(0, item["default"])
            setattr(self, item["entry_attr"], entry)

            def make_update_icon(icon_widget, entry_widget, color_attr):
                def update(event=None):
                    color = entry_widget.get()
                    try:
                        icon_widget.config(bg=color)
                        setattr(self, color_attr, color)
                    except:
                        pass
                return update

            entry.bind("<KeyRelease>", make_update_icon(icon, entry, item["color_attr"]))
            make_update_icon(icon, entry, item["color_attr"])()

            ttk.Button(
                frame_color, text="取色", width=5,
                command=lambda i=item: self.pick_region_color(
                    i["region_key"],
                    getattr(self, i["entry_attr"]),
                    getattr(self, i["icon_attr"]),
                    i["color_attr"]
                )
            ).pack(side=tk.LEFT, padx=2)
        master_cb.pack(side=tk.LEFT, anchor='nw', padx=5, pady=2)
        




    def create_config_frame(self):
        frame = ttk.LabelFrame(self.root, text="监控参数")
        frame.pack(pady=10, padx=10, fill="x")

        ttk.Label(frame, text="目标价格A:").grid(row=0, column=0, padx=5)
        self.target_digit_A = ttk.Entry(frame, width=5)
        self.target_digit_A.grid(row=0, column=1, padx=5, pady=1, sticky=tk.W)

        ttk.Label(frame, text="目标价格B:").grid(row=0, column=2, padx=5)
        self.target_digit_B = ttk.Entry(frame, width=5)
        self.target_digit_B.grid(row=0, column=3, padx=5, pady=1, sticky=tk.W)

        ttk.Label(frame, text="成功关键词:").grid(row=1, column=0, padx=5)
        self.success_keyword = ttk.Entry(frame)
        self.success_keyword.insert(0, "购买成功")
        self.success_keyword.grid(row=1, column=1, padx=5, pady=1, sticky=tk.W)

        ttk.Label(frame, text="失败关键词:").grid(row=1, column=2, padx=5)
        self.fail_keyword = ttk.Entry(frame)
        self.fail_keyword.insert(0, "库存不足")
        self.fail_keyword.grid(row=1, column=3, padx=5, pady=1, sticky=tk.W)

        # 模板加载按钮
        template_frame = ttk.Frame(frame)
        template_frame.grid(row=2, column=0, columnspan=4, sticky=tk.W, padx=5, pady=2)

        self.template_status = ttk.Label(
            template_frame,
            text="✖ 模板未加载",
            foreground="red"
        )
        self.template_status.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(template_frame, text="选择模板文件夹", command=self.load_digit_templates).pack(
            side=tk.LEFT)
        
        # 是否为子弹的勾选框
        global is_bullet_var
        is_bullet_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(template_frame, text="是否为子弹(一次购买200发)", variable=is_bullet_var).pack(side=tk.LEFT, padx=50)

        
    
    def create_purchase_limit_frame(self):
        frame = ttk.LabelFrame(self.root, text="购买限制设置")
        frame.pack(pady=10, padx=10, fill="x")

        ttk.Label(frame, text="成功次数限制:").pack(side=tk.LEFT)
        self.max_success_entry = ttk.Entry(frame, width=5)
        self.max_success_entry.pack(side=tk.LEFT, padx=5, pady=1)
        self.max_success_entry.insert(0, "0")

        self.action_var = tk.StringVar(value="停止")
        ttk.Label(frame, text="达到次数后:").pack(side=tk.LEFT, padx=(10,0))
        ttk.Radiobutton(frame, text="停止", variable=self.action_var, value="停止").pack(side=tk.LEFT)
        ttk.Radiobutton(frame, text="关机", variable=self.action_var, value="关机").pack(side=tk.LEFT)

    def perform_shutdown(self):
        try:
            self.log("将在5秒后关机...")
            os.system('shutdown /s /t 5')
        except Exception as e:
            self.log(f"关机失败: {str(e)}")
    
    def check_purchase_result(self):
        try:
            # 检测成功提示
            success_region = self.coords["成功提示"]
            img = ImageGrab.grab(bbox=success_region).convert("L")
            custom_config = r'--oem 3 --psm 6 -l chi_sim'
            text = pytesseract.image_to_string(img, config=custom_config).strip()
            
            success_keyword = self.success_keyword.get().strip()
            if success_keyword and success_keyword in text:
                self.log(f"检测到成功提示: {text}")
                return True
            
            # 检测失败提示
            fail_region = self.coords["失败提示"]
            img_fail = ImageGrab.grab(bbox=fail_region).convert("L")
            fail_text = pytesseract.image_to_string(img_fail, config=custom_config).strip()
            fail_keyword = self.fail_keyword.get().strip()
            if fail_keyword and fail_keyword in fail_text:
                self.log(f"⚠️ 购买失败: {fail_text}")
            
            return False
        except Exception as e:
            self.log(f"结果检测失败: {str(e)}")
            return False

    def create_log_area(self):
        frame = ttk.LabelFrame(self.root, text="操作日志")
        frame.pack(pady=10, padx=10, fill="both", expand=True)
        self.log_area = scrolledtext.ScrolledText(frame, height=10)
        self.log_area.pack(fill="both", expand=True)

    def log(self, message):
        self.log_area.insert(
            tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_area.see(tk.END)

    def load_digit_templates(self):
        folder = filedialog.askdirectory(title="选择数字模板文件夹")
        if not folder:
            return

        self.digit_templates.clear()

        for i in range(10):
            path = f"{folder}/{i}.png"
            template = cv2.imread(path, 0)
            if template is None:
                self.log(f"加载模板图片失败: {path}")
                continue
            self.digit_templates[i] = template

        if len(self.digit_templates) < 10:
            self.log("警告：部分模板图片加载失败，识别可能不准确！")
        else:
            self.log("模板图片加载完成！")
        if len(self.digit_templates) == 10:
            self.template_status.config(text="✔ 模板已加载", foreground="green")
        else:
            self.template_status.config(
            text=f"⚠ 已加载{len(self.digit_templates)}/10个模板", 
            foreground="orange"
        )

    def stop_monitoring(self):
        global is_running
        is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.log("监控已停止")
        self.update_overlay()
    
    def create_control_buttons(self):
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=10)

    # 原有开始/停止按钮
        self.start_btn = ttk.Button(
            btn_frame, text="开始监控", command=self.start_monitoring)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(
            btn_frame, text="停止监控", command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

    # 新增测试识别按钮
        self.test_btn = ttk.Button(
            btn_frame, text="测试识别", command=self.test_recognition)
        self.test_btn.pack(side=tk.LEFT, padx=5)
    
    def test_recognition(self):
        """测试识别功能"""
        try:
            digitA = self.ocr_digit_by_template(self.coords["价格区域A"])
            digitB = self.ocr_digit_by_template(self.coords["价格区域B"])
            
            result = []
            for name, value in [("A", digitA), ("B", digitB)]:
                if value == -1:
                    result.append(f"数字{name}识别失败")
                elif not (0 <= value <= 9):
                    result.append(f"数字{name}无效：{value}")
                else:
                    result.append(f"数字{name}：{value}")
                    
            self.log("测试结果：" + "，".join(result))
        except Exception as e:
            self.log(f"测试识别失败：{str(e)}")  # 确保这里的 self 在方法内部
    

    def validate_coords(self, coords):
        try:
            screen_width = win32api.GetSystemMetrics(0)
            screen_height = win32api.GetSystemMetrics(1)
            return (0 <= coords[0] <= screen_width) and (0 <= coords[1] <= screen_height)
        except:
            return False

    def monitoring_loop(self):
        global is_running
        while is_running:
            try:
                self.click(15, 15, clicks=1)  # 点击屏幕左上角，避免误触其他区域
                # 刷新操作
                self.log("执行ESC刷新 monitoring_loop...")
                with self.coord_lock:
                    
                    win32api.keybd_event(win32con.VK_ESCAPE, 0, 0, 0)  # 按下ESC
                    win32api.keybd_event(win32con.VK_ESCAPE, 0, win32con.KEYEVENTF_KEYUP, 0)  # 松开ESC
                    time.sleep(0.2)  # 等待刷新完成

                    refresh_region = self.coords["刷新按钮"]
                    click_x = (refresh_region[0] + refresh_region[2]) // 2
                    click_y = (refresh_region[1] + refresh_region[3]) // 2

                if not self.validate_coords((click_x, click_y)):
                    self.log("刷新坐标无效！")
                    break

                # 检测刷新按钮颜色（循环直到检测到正确颜色）
                while True:
                    if not is_running:
                        break # 如果监控已停止，退出循环
                    color = self.pick_region_color("刷新按钮")
                    if color and color.lower() == self.refresh_color.lower():
                        self.log("刷新按钮颜色正确")
                        break
                    else:
                        self.log("刷新按钮未找到，等待刷新...")
                        time.sleep(0.2)

                # 执行点击进入交易界面
                self.click(click_x, click_y)
                time.sleep(0.2)

                # 检测购买数图标颜色
                while True:
                    if not is_running:
                        break # 如果监控已停止，退出循环
                    icon_color = self.pick_region_color("购买数图标")
                    if icon_color and icon_color.lower() == self.buy_icon_color.lower():
                        self.log("购买数图标颜色正确")
                        break
                    else:
                        self.log("购买数图标未找到，等待刷新...")
                        time.sleep(0.2)

                # 价格识别
                digitA = self.ocr_digit_by_template(self.coords["价格区域A"])
                digitB = self.ocr_digit_by_template(self.coords["价格区域B"])

                if digitA == -1 or digitB == -1:
                    self.log("价格识别失败，跳过本次循环")
                    continue

                try:
                    recognized_price = int(f"{digitA}{digitB}")
                    target_price = int(f"{self.target_digit_A.get()}{self.target_digit_B.get()}")
                except ValueError:
                    self.log("价格格式错误")
                    continue

                self.log(f"当前价格: {recognized_price}, 目标价格: {target_price}")

                if recognized_price <= target_price:
                    buy_region = self.coords['购买按钮']
                    buy_x = (buy_region[0] + buy_region[2]) // 2
                    buy_y = (buy_region[1] + buy_region[3]) // 2

                    # 点击购买数量
                    if is_bullet_var.get():
                        self.log("检测到购买子弹模式，点击购买数量区域")
                        quantity_region = self.coords['购买数量']
                        quantity_x = (quantity_region[0] + quantity_region[2]) // 2
                        quantity_y = (quantity_region[1] + quantity_region[3]) // 2
                        time.sleep(0.1)  # 等待点击稳定
                        self.click(quantity_x, quantity_y, clicks=1)  # 点击购买数量区域
                        self.log("已点击购买数量区域200")
                        time.sleep(0.2)  # 等待输入框激活
                    
                    # 点击购买按钮
                    if self.click(buy_x, buy_y, clicks=2):
                        time.sleep(1)  # 等待提示出现
                        if self.check_purchase_result():
                            with self.count_lock:
                                self.success_count += 1
                                current_count = self.success_count
                                try:
                                    max_count = int(self.max_success_entry.get())
                                except:
                                    max_count = 0

                            self.log(f"✅ 成功购买！累计次数: {current_count}/{max_count if max_count >0 else '无限制'}")

                            if max_count > 0 and current_count >= max_count:
                                action = self.action_var.get()
                                self.log(f"达到目标次数，执行操作: {action}")
                                self.stop_monitoring()
                                if action == "关机":
                                    self.root.after(1000, self.perform_shutdown)
                                return

                time.sleep(0.2)

            except Exception as e:
                self.log(f"监控循环异常: {str(e)}")
                time.sleep(2)

    def start_monitoring(self):
        global is_running
        if not self.check_templates_loaded():
            return
        if not is_running:
            with self.count_lock:
                self.success_count = 0
            is_running = True
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.log("启动监控...")
            threading.Thread(target=self.monitoring_loop, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = AutoTraderGUI(root)
    root.mainloop()
