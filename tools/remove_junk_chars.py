# utils/remove_junk_chars.py
import re

def clean_repeated_chars(text: str) -> str:
    """
    清洗连续重复的无意义字符。
    例如: "Test......" -> "Test"
    """
    if not isinstance(text, str):
        return text
    # 示例：去除连续超过3个的 . 或 - 或 _
    text = re.sub(r'[\.\-\_]{3,}', '', text)
    return text.strip()