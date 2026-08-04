# tools/boc/string_cleaner.py
import re


def remove_repetitive_punctuation(text: str, threshold: int = 3) -> str:
    """
    去除连续重复的标点符号（如分割线、装饰线）。
    同时去除 BOC 特有的 "─" 干扰符（即使不连续）。

    Args:
        text: 单元格文本
        threshold: 连续出现多少次视为干扰线
    """
    if not isinstance(text, str):
        return str(text) if text is not None else ""

    # 1. 针对 BOC 的特殊处理：移除所有 "─" (U+2500 Box Drawings Light Horizontal)
    # 因为在 BOC 对账单里，这个符号只出现在表头装饰里，绝不会出现在金额或摘要里
    cleaned = text.replace("─", "")

    # 2. 去除连续的普通减号或下划线 (例如 "-------")
    # pattern: 匹配 - 或 _ 连续出现 threshold 次以上
    pattern = r'[-_]{' + str(threshold) + r',}'
    cleaned = re.sub(pattern, '', cleaned)

    return cleaned.strip()


def is_english_start(text: str) -> bool:
    """
    判断字符串是否以英文字母开头（忽略大小写和空格）。
    用于识别 'No.', 'Date', 'Bk.D.' 等英文表头行。
    """
    if not isinstance(text, str): return False
    # 去除首尾空格后，检查第一个字符是否为 A-Z
    clean_t = text.strip()
    if not clean_t: return False
    return clean_t[0].isalpha()