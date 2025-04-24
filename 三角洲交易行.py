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
digit_templates = {}



class AutoTraderGUI:
    def __init__(self, root):
        self.root = root
        root.title("游戏交易行监控助手 v2.1 by：文真则")
        root.geometry("700x600")
        root.attributes("-topmost", True)
        self.digit_templates = {}
        
        # 初始化OCR路径（根据实际安装位置调整）
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        
        self.default_coords = {
            '刷新按钮': (210, 330, 294, 414),
            '价格区域A': (0, 0, 0, 0),
            '价格区域B': (0, 0, 0, 0),
            '购买按钮': (2964, 1803, 3560, 1920),
            '成功提示': (1515, 300, 2324, 375),
            '失败提示': (1596, 300, 2243, 376)
        }
        self.coords = self.default_coords.copy()
        self.coord_lock = threading.Lock()
        self.success_count = 0
        self.count_lock = threading.Lock()

        self.create_coord_frame()
        self.create_config_frame()
        self.create_purchase_limit_frame()
        self.create_log_area()
        self.create_control_buttons()
        self.create_preset_buttons()
        self.create_threshold_setting()
        self.create_overlay()
        self.create_status_bar()

        keyboard.add_hotkey('ctrl+shift+alt+s', self.stop_monitoring)
        self.log("全局快捷键 Ctrl+Shift+Alt+S 已注册")

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
  
    def create_status_bar(self):
        status_frame = ttk.Frame(self.root)
        status_frame.pack(pady=5, padx=10, fill="x")
        
        self.template_status = ttk.Label(
            status_frame, 
            text="✖ 模板未加载", 
            foreground="red"
        )
        self.template_status.pack(side=tk.LEFT)
        
        self.hotkey_hint = ttk.Label(
            status_frame,
            text="停止快捷键：Ctrl+Shift+Alt+S",
            foreground="gray"
        )
        self.hotkey_hint.pack(side=tk.RIGHT)

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
        for key in ["价格区域A", "价格区域B", "购买按钮", "成功提示", "失败提示"]:
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

    def create_preset_buttons(self):
        preset_frame = ttk.Frame(self.root)
        preset_frame.pack(pady=5, padx=10, fill="x")

        presets = {
            "七位数": {
                "A": (347, 1870, 370, 1910),
                "B": (379, 1870, 401, 1910)
            },
            "六位数": {
                "A": (365, 1870, 385, 1910),
                "B": (386, 1870, 406, 1910)
            },
            "四位数": {
                "A": (386, 1870, 408, 1910),
                "B": (418, 1870, 439, 1910)
            },
            "三位数": {
                "A": (401, 1870, 424, 1910),
                "B": (424, 1870, 446, 1910)
            }
        }

        for name, coords in presets.items():
            btn = ttk.Button(preset_frame, text=name,
                             command=lambda c=coords: self.fill_preset_coords(c))
            btn.pack(side=tk.LEFT, padx=5)

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
    
    def create_coord_frame(self):
        frame = ttk.LabelFrame(self.root, text="坐标设置 (格式: X1,Y1,X2,Y2)")
        frame.pack(pady=10, padx=10, fill="x")

        self.coord_entries = {}

        for key in self.default_coords:
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=2)
            

            ttk.Label(row, text=key, width=12).pack(side=tk.LEFT)

            entries = []
            for i in range(4):
                entry = ttk.Entry(row, width=5)
                entry.pack(side=tk.LEFT, padx=2)
                entry.insert(0, str(self.default_coords[key][i]))
                entries.append(entry)

            self.coord_entries[key] = entries

    def create_config_frame(self):
        frame = ttk.LabelFrame(self.root, text="监控参数")
        frame.pack(pady=10, padx=10, fill="x")

        ttk.Label(frame, text="目标价格A:").grid(row=0, column=0, padx=5)
        self.target_digit_A = ttk.Entry(frame, width=5)
        self.target_digit_A.grid(row=0, column=1, padx=5)

        ttk.Label(frame, text="目标价格B:").grid(row=0, column=2, padx=5)
        self.target_digit_B = ttk.Entry(frame, width=5)
        self.target_digit_B.grid(row=0, column=3, padx=5)

        ttk.Label(frame, text="成功关键词:").grid(row=1, column=0, padx=5)
        self.success_keyword = ttk.Entry(frame)
        self.success_keyword.insert(0, "购买成功")
        self.success_keyword.grid(row=1, column=1, padx=5)

        ttk.Label(frame, text="失败关键词:").grid(row=1, column=2, padx=5)
        self.fail_keyword = ttk.Entry(frame)
        self.fail_keyword.insert(0, "库存不足")
        self.fail_keyword.grid(row=1, column=3, padx=5)

        ttk.Button(frame, text="选择模板文件夹", command=self.load_digit_templates).grid(
            row=2, column=0, columnspan=4, pady=5)
    
    def create_purchase_limit_frame(self):
        frame = ttk.LabelFrame(self.root, text="购买限制设置")
        frame.pack(pady=10, padx=10, fill="x")

        ttk.Label(frame, text="成功次数限制:").pack(side=tk.LEFT)
        self.max_success_entry = ttk.Entry(frame, width=5)
        self.max_success_entry.pack(side=tk.LEFT, padx=5)
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


        global is_running
        while is_running:
            try:
               self.log("执行刷新...")
               refresh_region = self.coords["刷新按钮"]
               click_x = (refresh_region[0] + refresh_region[2]) // 2
               click_y = (refresh_region[1] + refresh_region[3]) // 2
               self.click(click_x, click_y)  # 使用统一的win32api点击方法
               time.sleep(0.5)  # 仅保留必要的最小等待时间

                # 识别价格
               digitA = self.ocr_digit_by_template(self.coords["价格区域A"])
               digitB = self.ocr_digit_by_template(self.coords["价格区域B"])

                # 组合价格并比较
               recognized_price = str(digitA) + str(digitB)
               try:
                    current_price = int(recognized_price)
                    target_price = int(self.target_digit_A.get() + self.target_digit_B.get())
                    if current_price <= target_price:
                        # 获取购买按钮坐标
                        buy_region = self.coords['购买按钮']
                        buy_x = (buy_region[0] + buy_region[2]) // 2
                        buy_y = (buy_region[1] + buy_region[3]) // 2
                        
                        # 执行点击
                        self.click(buy_x, buy_y)
               except ValueError:
                    self.log("价格转换失败")
               time.sleep(0.5)  # 循环间隔缩短
            except Exception as e:
                self.log(f"主流程异常: {str(e)}")

        self.stop_monitoring()

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
    

        global is_running
        while is_running:
            try:
                self.log("执行刷新...")
                pyautogui.click(*self.coords["刷新按钮"][:2])
                time.sleep(0.3)  # 适当缩短等待时间

                # 识别价格
                digitA = self.ocr_digit_by_template(self.coords["价格区域A"])
                digitB = self.ocr_digit_by_template(self.coords["价格区域B"])

                # 验证逻辑
                validation_errors = []
                if not (0 <= digitA <= 9):
                    validation_errors.append("数字A不是个位数")
                if not (0 <= digitB <= 9):
                    validation_errors.append("数字B不是个位数")
                if digitA == 0:
                    validation_errors.append("数字A为0（非法值）")
                if validation_errors:
                    self.log("验证失败：" + "，".join(validation_errors))
                    continue

                # 组合价格并比较
                recognized_price = str(digitA) + str(digitB)
                try:
                    current_price = int(recognized_price)
                    target_price = int(self.target_digit_A.get() + self.target_digit_B.get())
                    if current_price <= target_price:
                        buy_region = self.coords['购买按钮']
                        buy_x = (buy_region[0] + buy_region[2]) // 2
                        buy_y = (buy_region[1] + buy_region[3]) // 2
                        
                        # 执行点击（支持双击）
                        self.click(buy_x, buy_y, clicks=2)
                        self.log(f"已执行双击操作 ({buy_x}, {buy_y})")
                        
                    else:
                        self.log(f"价格 {recognized_price} 高于目标价格 {target_price}，不购买")
                except ValueError:
                    self.log("价格转换失败")
                time.sleep(0.5)  # 循环间隔
            except Exception as e:
                self.log(f"主流程异常: {str(e)}")

        """使用 win32api 执行可靠的双击操作"""
        try:
            win32api.SetCursorPos((x, y))
            for _ in range(clicks):
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
                time.sleep(0.05)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)
                time.sleep(0.1)  # 点击间隔
            self.log(f"成功执行 {clicks} 次点击 ({x}, {y})")
            return True
        except Exception as e:
            self.log(f"点击失败：{str(e)}")
            return False

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
                # 刷新操作
                self.log("执行刷新...")
                with self.coord_lock:
                    refresh_region = self.coords["刷新按钮"]
                    click_x = (refresh_region[0] + refresh_region[2]) // 2
                    click_y = (refresh_region[1] + refresh_region[3]) // 2

                if not self.validate_coords((click_x, click_y)):
                    self.log("刷新坐标无效！")
                    continue

                self.click(click_x, click_y)
                time.sleep(0.5)

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

                time.sleep(1)

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
