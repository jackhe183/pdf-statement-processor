# config.py
import pathlib
import logging

# --- 路径配置 ---
PROJECT_ROOT = pathlib.Path(__file__).parent.absolute()

# 输入文件夹
INPUT_FOLDER = PROJECT_ROOT / "data" / "v125待优化"

# 输出根目录
OUTPUT_FOLDER = PROJECT_ROOT / "data" / "v125待优化_output"

# 具体的三个平级输出目录
DEBUG_IMG_DIR = OUTPUT_FOLDER / "Debug_Images"
DEBUG_EXCEL_DIR = OUTPUT_FOLDER / "Debug_Excel"
RESULT_DIR = OUTPUT_FOLDER / "Excel_Result"

# 调试开关
ENABLE_DEBUG_IMAGE = True
ENABLE_DEBUG_EXCEL = True

# --- 日志配置 ---
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = logging.INFO

# --- 默认表格提取参数 ---
DEFAULT_TABLE_SETTINGS = {
    "vertical_strategy": "lines", 
    "horizontal_strategy": "lines",
    "intersection_y_tolerance": 10,
}