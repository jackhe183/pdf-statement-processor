# main.py
import logging
import sys
import pathlib

# 添加项目根目录到路径
PROJECT_ROOT = pathlib.Path(__file__).parent.absolute()
sys.path.append(str(PROJECT_ROOT))

import config
from router.get_pipeline_class import get_pipeline_class


def main():
    logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)

    # 可选：运行前清理旧的调试文件，保持清爽
    # import shutil
    # if config.OUTPUT_FOLDER.exists():
    #     shutil.rmtree(config.DEBUG_IMG_DIR, ignore_errors=True)
    #     shutil.rmtree(config.DEBUG_EXCEL_DIR, ignore_errors=True)

    logging.info("🚀 启动处理程序...")
    logging.info(f"📂 输入: {config.INPUT_FOLDER}")
    logging.info(f"📂 输出: {config.OUTPUT_FOLDER}")

    pdf_files = list(config.INPUT_FOLDER.glob("*.pdf"))

    if not pdf_files:
        logging.warning("⚠️ 目录下未找到 PDF 文件。")
        return

    for pdf_file in pdf_files:
        try:
            PipelineClass = get_pipeline_class(pdf_file)
            pipeline = PipelineClass(pdf_file)
            pipeline.run()
        except ValueError as e:
            logging.warning(f"⏩ 跳过: {pdf_file.name} ({e})")
        except Exception as e:
            logging.error(f"❌ 严重错误 {pdf_file.name}: {e}", exc_info=True)

    logging.info("🏁 所有任务处理完成。")


if __name__ == "__main__":
    main()


