# tools/watermark_remover.py
import pdfplumber.page
from typing import Dict, Any, Union, Optional, List, Tuple
import logging


def _is_black_or_dark(color: Optional[Union[List, Tuple, int, float]], threshold: float = 0.5) -> bool:
    """
    判断颜色是否为深色。
    threshold: 阈值调高到 0.5，意味着容忍度更高。
    只要 R, G, B 中没有一个分量超过 0.5 (128/255)，就认为是深色。
    纯红 (1,0,0) -> Max 1.0 > 0.5 -> 剔除
    纯蓝 (0,0,1) -> Max 1.0 > 0.5 -> 剔除
    深蓝 (0,0,0.4) -> Max 0.4 < 0.5 -> 保留 (有些银行标题是深蓝)
    黑色 (0,0,0) -> 保留
    """
    if color is None:
        return True

    values = []
    if isinstance(color, (int, float)):
        values = [color]
    elif isinstance(color, (list, tuple)):
        values = list(color)

    normalized_values = []
    for v in values:
        if v > 1.0:
            normalized_values.append(v / 255.0)

        else:
            normalized_values.append(v)

    if len(normalized_values) in [1, 3]:
        return max(normalized_values) < threshold
    elif len(normalized_values) == 4:
        c, m, y, k = normalized_values
        if k < 0.5: return False  # CMYK 中 K 必须够黑
        return True

    return True


def _watermark_predicate(obj: Dict[str, Any]) -> bool:
    """
    过滤器：保留深色对象，剔除浅色/彩色干扰。
    """
    obj_type = obj.get("object_type")

    # --- 1. 图片处理 (新增) ---
    # 如果是图片，pdfplumber 无法判断图片内部颜色。
    # 策略 A: 暴力剔除所有图片 (通常财务表格里不需要图片，图片都是Logo或广告)
    if obj_type == "image":
        return False

        # 策略 B: 如果你非要保留图片，就 return True，但后果是红章会挡住表格线
    # if obj_type == "image": return True

    # --- 2. 文本和线条处理 ---
    stroke = obj.get("stroking_color")
    fill = obj.get("non_stroking_color")

    # 文本 (char) 通常只看填充色
    if obj_type == "char":
        if not _is_black_or_dark(fill):
            return False

    # 线条/矩形
    elif obj_type in ["line", "rect", "curve"]:
        # 只要有一边是深色就保留 (防止表格线漏删)
        is_stroke_dark = _is_black_or_dark(stroke)
        # 矩形特殊处理：如果是浅色填充背景，剔除
        if obj_type == "rect" and fill is not None and not _is_black_or_dark(fill):
            return False

        # 既无深色描边，也无深色填充 -> 剔除
        if not is_stroke_dark and (fill is not None and not _is_black_or_dark(fill)):
            return False

    return True


def remove_pdf_watermarks(page: pdfplumber.page.Page) -> pdfplumber.page.Page:
    return page.filter(_watermark_predicate)