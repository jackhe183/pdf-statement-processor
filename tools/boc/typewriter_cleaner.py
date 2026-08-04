# tools/boc/typewriter_cleaner.py
import logging
from typing import List


def reconstruct_and_split_by_delimiter(tables: List[List[List[str]]], delimiter: str = "|") -> List[List[str]]:
    """
    [打字机风格专用]
    将 pdfplumber 提取的碎片化数据重新组合，并严格按照指定分隔符（如 '|'）进行拆分。

    Args:
        tables: extract_tables 的原始输出
        delimiter: 分隔符，默认为 '|'
    """
    cleaned_rows = []

    # 1. 展平所有表格的所有行 (Flatten)
    # pdfplumber 在 text 策略下，可能会把一页识别成多个 table，我们需要把它们串起来
    raw_rows = [row for table in tables for row in table]

    for row in raw_rows:
        # 2. 将当前行的所有单元格合并成一个长字符串
        # 这一步是为了消除 pdfplumber 对空格或细微间距的误判
        # 例如: ["|", " 2024 ", "| 100.00"] -> "| 2024 | 100.00"
        full_line_text = "".join([str(x) if x else "" for x in row])
        full_line_text = full_line_text.strip()

        # 3. 检查是否有分隔符
        # 如果这行连一个 "|" 都没有，通常是页眉页脚或垃圾行
        if delimiter not in full_line_text:
            continue

        # 4. 按分隔符拆分
        # 注意： "| A | B |" split('|') 会得到 ['', 'A', 'B', '']
        parts = full_line_text.split(delimiter)

        # 5. 简单清洗拆分后的每一项 (去空格)
        new_row = [p.strip() for p in parts]

        # 过滤掉全空的行
        # (有时 split 产生全是空字符串的列表)
        if any(new_row):
            cleaned_rows.append(new_row)

    return cleaned_rows