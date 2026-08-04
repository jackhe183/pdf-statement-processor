# server.py
# --- 标准库导入 ---
import shutil
import uuid
import logging
import pathlib
import os

# --- 第三方库导入 ---
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

# --- 本地应用/库导入 ---
# 确保项目根目录在 sys.path 中 (如果 server.py 在根目录则不需要特殊处理，但在同级包引用时通常需要)
import sys

PROJECT_ROOT = pathlib.Path(__file__).parent.absolute()
sys.path.append(str(PROJECT_ROOT))

import config
from router.get_pipeline_class import get_pipeline_class

# --- 初始化 ---
app = FastAPI(title="PDF to Excel Processor", version="1.0")

# 配置日志
logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger("API")

# 确保输入输出目录存在
# 我们新建一个专门的临时上传目录，避免污染 config.INPUT_FOLDER
TEMP_UPLOAD_DIR = config.PROJECT_ROOT / "data" / "api_uploads"
TEMP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
config.RESULT_DIR.mkdir(parents=True, exist_ok=True)


def cleanup_files(file_paths: list[pathlib.Path]):
    """后台任务：清理临时文件"""
    for path in file_paths:
        try:
            if path.exists():
                os.remove(path)
                logger.info(f"🧹 已清理临时文件: {path.name}")
        except Exception as e:
            logger.warning(f"⚠️ 清理文件失败 {path}: {e}")


@app.post("/process_pdf", summary="上传PDF并获取Excel结果")
def process_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    接收 PDF 文件 -> 保存 -> 运行 Pipeline -> 返回 Excel 文件
    """
    # 1. 生成唯一文件名，防止并发冲突
    # 使用 UUID 防止文件名重复
    file_ext = pathlib.Path(file.filename).suffix
    if file_ext.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="只支持 PDF 文件")

    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    input_path = TEMP_UPLOAD_DIR / unique_filename

    # 2. 保存上传的文件到磁盘
    try:
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"📥 接收文件: {file.filename} -> 保存为: {input_path}")
    except Exception as e:
        logger.error(f"❌ 文件保存失败: {e}")
        raise HTTPException(status_code=500, detail="文件上传保存失败")

    # 3. 运行 Pipeline 逻辑
    try:
        # 获取对应的 Pipeline 类
        PipelineClass = get_pipeline_class(input_path)
        pipeline = PipelineClass(input_path)

        # 运行处理
        # 注意：这里的 run() 是同步阻塞的。
        # 在 FastAPI 中直接定义 def (而不是 async def) 会让它在线程池中运行，
        # 这对于 CPU 密集型任务是合适的，不会阻塞主事件循环。
        pipeline.run()

        # 4. 定位输出文件
        # 假设 pipeline 的逻辑是将 input_filename.pdf 变成 input_filename.xlsx 存放在 RESULT_DIR
        # 你可能需要根据实际的 pipeline 逻辑调整这里的寻找方式
        expected_output_name = input_path.stem + ".xlsx"  # 假设是同名 excel
        output_path = config.RESULT_DIR / expected_output_name

        # 如果你的 Pipeline 修改了文件名（例如去掉了 UUID），你需要在这里适配逻辑
        # 这里假设 Pipeline 比较智能，或者我们可以遍历文件夹找到最新生成的文件
        if not output_path.exists():
            # 尝试一种兜底策略：有些 pipeline 可能会保留原始文件名而不是 UUID
            # 这里需要根据你的具体 Pipeline 代码逻辑来定
            raise FileNotFoundError(f"未找到预期的输出文件: {output_path}")

        logger.info(f"✅ 处理完成，准备返回: {output_path}")

        # 5. 返回文件
        # 使用 BackgroundTasks 在文件发送后清理输入文件（输出文件通常保留或定期清理）
        # 如果你想连生成的 Excel 也删掉，把 output_path 也加进去
        background_tasks.add_task(cleanup_files, [input_path])

        return FileResponse(
            path=output_path,
            filename=f"processed_{file.filename.replace('.pdf', '.xlsx')}",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except ValueError as e:
        logger.warning(f"⏩ 无法处理的文件: {e}")
        raise HTTPException(status_code=400, detail=f"无法识别该银行或格式: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 处理出错: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@app.get("/", summary="健康检查")
def root():
    return {"status": "ok", "message": "PDF Pipeline Server is running"}


if __name__ == "__main__":
    # 允许直接运行 python server.py 启动
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)