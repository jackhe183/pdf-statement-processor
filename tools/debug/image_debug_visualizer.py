# tools/image_debug_visualizer.py
import pathlib
import pdfplumber.page
import logging


def save_debug_image(original_page: pdfplumber.page.Page,
                     target_page: pdfplumber.page.Page,
                     settings: dict,
                     output_path: pathlib.Path):
    """
    绘制并保存调试图片 (全页视角)。

    视觉元素说明：
    1. 底图：完整的原始页面 (Full Page)。
    2. 🟡 黄色小框：识别到的所有文字 (Words)。
    3. 🔴 红色线条：TableFinder 识别到的表格线 (基于 settings)。
    4. 🔵 蓝色粗框：实际裁剪区域 (Crop Box)。框内才是 extract_tables 处理的区域。
    """
    try:
        # 1. 使用【原始全页】生成底图，这样才能看到被裁掉的部分
        im = original_page.to_image(resolution=150)

        # 2. 绘制 TableFinder 调试线 (红色)
        # 我们在原图上应用 settings，看看在该策略下，全页的线条识别情况
        # 这样有助于判断：是否因为 crop 切掉了某根线导致识别错误
        im.debug_tablefinder(table_settings=settings)

        # 3. 绘制所有文字 (黄色)
        # 让你看清页眉页脚的文字在哪里
        im.draw_rects(original_page.extract_words(), stroke="yellow", stroke_width=1)

        # 4. [核心] 绘制裁剪区域 (蓝色粗框)
        # target_page.bbox 包含了裁剪后的坐标 (x0, top, x1, bottom)
        # 我们把它画在原图上，框内就是保留的数据，框外就是被切掉的垃圾
        if target_page.bbox:
            crop_rect = {
                "x0": target_page.bbox[0],
                "top": target_page.bbox[1],
                "x1": target_page.bbox[2],
                "bottom": target_page.bbox[3]
            }
            im.draw_rect(crop_rect, stroke="blue", stroke_width=5, fill=None)

        # 5. 保存
        output_path.parent.mkdir(parents=True, exist_ok=True)
        im.save(output_path)
        logging.info(f"     🖼️ 调试图已保存(含裁剪框): {output_path.name}")

    except Exception as e:
        logging.error(f"     ❌ 保存调试图片失败 {output_path.name}: {e}")