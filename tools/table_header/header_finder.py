# tools/table_header/header_finder.py
import pdfplumber.page
import logging
from typing import Optional, List


def find_header_position(page: pdfplumber.page.Page,
                         roi_bbox: Optional[List[float]] = None,
                         keywords: List[str] = None,
                         tolerance: int = 3) -> float:
    """
    寻找表头位置 (Top)。

    优先级策略：
    1. 关键词定位：如果找到包含 keywords 的行，取该行上方作为 Top。
    2. 物理框兜底：如果没有关键词，但提供了 roi_bbox，使用 roi_bbox[1]。
    3. 全页兜底：如果都没有，返回 0。

    Args:
        page: PDF 页面对象
        roi_bbox: locate_roi 返回的 [x0, top, x1, bottom]，作为基准参考
        keywords: 表头关键词列表
        tolerance: 字符合并容差
    """
    if keywords is None:
        keywords = ["摘要", "交易日期", "记账日期"]

    # --- 1. 尝试通过关键词寻找更精准的表头 ---
    words = page.extract_words(keep_blank_chars=True, x_tolerance=tolerance, y_tolerance=tolerance)

    # 按行分组
    rows = {}
    for w in words:
        row_key = round(w['top'] / 5) * 5
        if row_key not in rows: rows[row_key] = []
        rows[row_key].append(w)

    for row_y, row_words in sorted(rows.items()):
        line_text = "".join([w['text'] for w in sorted(row_words, key=lambda x: x['x0'])])

        for kw in keywords:
            if kw in line_text:
                # 找到表头！
                min_top = min([w['top'] for w in row_words])
                refined_top = max(0, min_top - 9)
                logging.info(f"     👀 [HeaderFinder] 命中关键词 '{kw}'，优化 Top: {refined_top:.2f}")
                return refined_top

    # --- 2. 关键词没找到，使用 roi_bbox 兜底 ---
    if roi_bbox:
        fallback_top = roi_bbox[1]
        logging.info(f"     ⚠️ [HeaderFinder] 未找到关键词，回退使用物理框 Top: {fallback_top:.2f}")
        return fallback_top

    # --- 3. 彻底没招了，从头开始 ---
    logging.info("     ⚠️ [HeaderFinder] 彻底定位失败，默认为页面顶部 0")
    return 0