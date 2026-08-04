# tools/table_footer/footer_finder.py

# --- 标准库导入 ---
import logging
import re
from typing import Optional, List, Dict, Any, Pattern, Tuple

# --- 第三方库导入 ---
import pdfplumber.page

# --- 配置区 ---
FOOTER_PATTERNS: List[Pattern] = [
    re.compile(r'第\s*\d+\s*页', re.IGNORECASE),
    re.compile(r'共\s*\d+\s*页', re.IGNORECASE),
    re.compile(r'Page\s*\d+\s*of\s*\d+', re.IGNORECASE),
    re.compile(r'打印时间', re.IGNORECASE),
    re.compile(r'打印日期', re.IGNORECASE),
    re.compile(r'制表人', re.IGNORECASE),
    re.compile(r'操作员', re.IGNORECASE),
    re.compile(r'审核', re.IGNORECASE),
    re.compile(r'合计', re.IGNORECASE),  # 根据需求开启或注释
    re.compile(r'总金额', re.IGNORECASE),
    re.compile(r'重要提示', re.IGNORECASE),
    re.compile(r'查询', re.IGNORECASE),
]


# --- 主入口函数 ---

def find_table_bottom_comprehensive(page: pdfplumber.page.Page,
                                    header_top: float,
                                    roi_bbox: Optional[List[float]] = None,
                                    sparsity_threshold: float = 20.0) -> float:
    """
    综合多种策略寻找表格底部 (Bottom)。

    逻辑流程：
    1. 【数据准备】：提取并整理行数据。
    2. 【独立执行】：分别计算 稀疏度建议值(Sparsity) 和 正则建议值(Regex)。
    3. 【决策融合】：
       - 优先采纳稀疏度检测到的断层。
       - 但必须经过正则校验：如果正则发现更靠上的页脚，说明稀疏度漏了，强制使用正则位置。
       - 如果两者都没找到，降级使用 ROI。
       - 最后全页兜底。

    Args:
        page: PDF 页面对象
        header_top: 表头的 Top 坐标
        roi_bbox: 模型预测框
        sparsity_threshold: 稀疏阈值

    Returns:
        float: 建议裁剪的 bottom 坐标。
    """
    # 1. 数据准备 (Data Preparation)
    candidate_rows_y, rows_map = _prepare_row_data(page, header_top)

    if not candidate_rows_y:
        logging.info("     ⚠️ [FooterFinder] 表头下方无文本内容，直接进入兜底流程。")
        return _strategy_fallback(roi_bbox, page.height)

    # 2. 策略执行 (Strategy Execution) - 互不干扰
    val_sparsity = _strategy_sparsity_scan(candidate_rows_y, rows_map, sparsity_threshold)
    val_regex = _strategy_regex_match(candidate_rows_y, rows_map)

    # 3. 决策逻辑 (Decision Making)

    # 情况 A: 稀疏度检测找到了断层
    if val_sparsity is not None:
        # 校验步骤：虽然找到了断层，但看看正则有没有在断层 *之上* 发现了页脚？
        # 如果正则发现的位置(val_regex) 比 断层位置(val_sparsity) 更小(更靠上)，
        # 说明稀疏度扫描可能把页脚当成了表格的一部分（或者断层不够明显），此时应以正则为准。
        if val_regex is not None and val_regex < val_sparsity:
            logging.info(
                f"     ⚖️ [FooterFinder] 决策: 稀疏度建议({val_sparsity:.2f}) 被 正则校验({val_regex:.2f}) 修正 (正则更靠上)。")
            return val_regex

        # 否则，信任稀疏度扫描的结果（它可能切除了表格和页脚之间的大片空白，比正则更精准）
        logging.info(f"     ✅ [FooterFinder] 决策: 采纳稀疏度扫描结果: {val_sparsity:.2f}")
        return val_sparsity

    # 情况 B: 稀疏度没找到断层，但正则找到了关键字
    if val_regex is not None:
        logging.info(f"     ✅ [FooterFinder] 决策: 稀疏度未命中，采纳正则匹配结果: {val_regex:.2f}")
        return val_regex

    # 情况 C: 两个智能策略都失效 -> 兜底
    logging.info("     🛡️ [FooterFinder] 决策: 智能策略均未命中，使用物理兜底。")
    return _strategy_fallback(roi_bbox, page.height)


# --- 子策略函数 (Sub-Strategies) ---

def _prepare_row_data(page: pdfplumber.page.Page, header_top: float) -> Tuple[List[int], Dict[int, List[Dict]]]:
    """工具函数：提取文字并按行聚类"""
    words = page.extract_words(x_tolerance=2, y_tolerance=2)
    if not words:
        return [], {}

    rows_map = {}
    for w in words:
        y_key = round(w['top'])
        if y_key not in rows_map:
            rows_map[y_key] = []
        rows_map[y_key].append(w)

    sorted_y = sorted(rows_map.keys())
    # 只取 header_top 之后的内容
    valid_y = [y for y in sorted_y if y > header_top + 2]

    return valid_y, rows_map


def _strategy_sparsity_scan(candidate_rows_y: List[int],
                            rows_map: Dict[int, List[Dict]],
                            threshold: float) -> Optional[float]:
    """策略一：稀疏度扫描。寻找第一个显著的行间距断层。"""

    # 遍历行寻找断层
    for i in range(len(candidate_rows_y) - 1):
        current_row_top = candidate_rows_y[i]
        next_row_top = candidate_rows_y[i + 1]

        # 当前行的实体底边 (取 max bottom)
        current_row_words = rows_map[current_row_top]
        current_row_bottom = max(w['bottom'] for w in current_row_words)

        # 计算 Gap (下一行顶 - 当前行底)
        gap = next_row_top - current_row_bottom

        if gap > threshold:
            cutoff_y = current_row_bottom + 5  # 留少许余量
            logging.info(
                f"     ✂️ [FooterFinder-Sparsity] 发现断层: Y={current_row_top} 后 Gap={gap:.2f} -> 建议Bottom={cutoff_y:.2f}"
            )
            return cutoff_y

    return None


def _strategy_regex_match(candidate_rows_y: List[int],
                          rows_map: Dict[int, List[Dict]]) -> Optional[float]:
    """策略二：正则字段匹配。寻找页脚关键字。"""

    for i, y_key in enumerate(candidate_rows_y):
        row_words = rows_map[y_key]
        row_text = "".join([w['text'] for w in row_words])

        # 检查是否匹配任一特征
        is_footer = False
        for pattern in FOOTER_PATTERNS:
            if pattern.search(row_text):
                logging.info(
                    f"     🧩 [FooterFinder-Regex] 捕获关键字 '{pattern.pattern}' 在 Y={y_key}")
                is_footer = True
                break

        if is_footer:
            # 找到页脚行，开始计算切割点
            if i == 0:
                # 极端情况：第一行就是页脚
                return float(y_key - 2)

            # 获取上一行（内容行）的数据
            prev_row_top = candidate_rows_y[i - 1]
            prev_row_words = rows_map[prev_row_top]
            prev_row_bottom = max(w['bottom'] for w in prev_row_words)  # 内容行底边

            current_row_top = min(w['top'] for w in row_words)  # 页脚行顶边

            # 紧贴内容底 + 呼吸缝隙
            padding = 5.0
            target_bottom = prev_row_bottom + padding

            # 确保不切进页脚里
            final_bottom = min(target_bottom, current_row_top)

            logging.info(
                f"     ✂️ [FooterFinder-Regex] 建议切割: 上一行底({prev_row_bottom:.2f}) -> 建议Bottom={final_bottom:.2f}")
            return final_bottom

    return None


def _strategy_fallback(roi_bbox: Optional[List[float]], page_height: float) -> float:
    """策略三 & 四：ROI 或 全页高度兜底"""
    if roi_bbox:
        logging.info(f"     🛡️ [FooterFinder-Fallback] 使用 ROI 底线: {roi_bbox[3]:.2f}")
        return roi_bbox[3]

    logging.info(f"     🛡️ [FooterFinder-Fallback] 使用页面高度: {page_height:.2f}")
    return float(page_height)


# 兼容旧代码调用
find_table_bottom_by_sparsity = find_table_bottom_comprehensive