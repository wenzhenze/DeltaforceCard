import PyInstaller.__main__
import shutil
import os

# 配置参数
APP_NAME = "三角洲交易助手"
MAIN_SCRIPT = "三角洲交易行.py"
ICON_PATH = "icon.ico" if os.path.exists("icon.ico") else None

# 修正：正确的文件添加格式
ADDITIONAL_FILES = [
    # 格式：(源文件, 目标目录)
    (os.path.join('tesseract', 'tesseract.exe'), 'tesseract'),
    (os.path.join('tesseract', 'tessdata'), 'tesseract/tessdata')
]

# 构建 PyInstaller 命令
params = [
    '--name', APP_NAME,
    '--onefile',
    '--windowed',
    # 删除原有的 templates 引用
    # '--add-data', 'templates;templates'  # 这行需要删除
]

# 添加附加文件（修正格式）
for src, dest in ADDITIONAL_FILES:
    # 正确格式：--add-data "源路径;目标路径"
    params += ['--add-data', f'{src};{dest}']

if ICON_PATH:
    params += ['--icon', ICON_PATH]

params.append(MAIN_SCRIPT)

# 执行打包
PyInstaller.__main__.run(params)

print(f"打包完成！可执行文件在: dist\\{APP_NAME}.exe")