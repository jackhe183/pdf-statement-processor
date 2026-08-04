# pipelines/boc_pipeline.py
import pdfplumber.page
import pandas as pd
import logging
import re
from typing import List, Optional, Dict, Any

from core.base_pipeline import BasePipeline
from tools.table_header.header_finder import find_header_position
from tools.table_footer.footer_finder import find_table_bottom_by_sparsity
from tools.table_cell.cell_cleaner import clean_cell_newlines, merge_hanging_rows
from tools.table_header.header_remover import remove_header_by_keyword
from tools.boc.typewriter_cleaner import reconstruct_and_split_by_delimiter
from tools.boc.string_cleaner import remove_repetitive_punctuation, is_english_start
from tools.decorators import timing_decorator, safe_execute


class BOCPipeline(BasePipeline):
    def __init__(self, pdf_path):
        super().__init__(pdf_path, bank_name="boc")

    # 标准列名
    STANDARD_HEADERS = [
        "序号", "记账日", "起息日", "交易类型", "凭证",
        "摘要/用途", "借方发生额", "贷方发生额", "余额",
        "机构/柜员/流水", "备注"
    ]

    def get_extract_settings(self, page) -> Dict[str, Any]:
        # BOC 是纯字符表格，必须用 text 策略
        return {
            "vertical_strategy": "text",
            "horizontal_strategy": "text",
            "snap_tolerance": 2
        }

    @timing_decorator("BOC数据清洗")
    @safe_execute(default_return=pd.DataFrame())
    def clean_data(self, tables: List[List[List[str]]], page_num: int) -> pd.DataFrame:
        """
        [BOC 清洗逻辑 - 修复版]
        """
        # 1. 重组并按 '|' 拆分
        rows = reconstruct_and_split_by_delimiter(tables, delimiter="|")
        if not rows: return pd.DataFrame()

        df = pd.DataFrame(rows)

        # 2. [关键步骤] 优先修正列结构
        # 因为 '|...|' split 后首尾通常是空串，必须先切掉，否则后面判断哪一列是英文会错位
        current_cols = len(df.columns)
        target_cols = len(self.STANDARD_HEADERS)

        if current_cols == target_cols + 2:
            # 典型情况：首尾各多一列空
            df = df.iloc[:, 1:-1]
        elif current_cols == target_cols + 1:
            # 判断第一列是否全空
            if df.iloc[:, 0].astype(str).str.strip().eq("").all():
                df = df.iloc[:, 1:]
            else:
                df = df.iloc[:, :-1]

        # 3. 全局字符清洗
        # 去除 '─' 和 '---'，把 '─记─账─' 变成 '记账'
        df = df.map(lambda x: remove_repetitive_punctuation(str(x)))
        df = clean_cell_newlines(df)

        # 4. 剔除中文表头
        # 现在的 keyword="记账" 应该能命中了
        df = remove_header_by_keyword(df, page_num, keyword="记账")

        # 5. [新增] 剔除英文副表头 (No. / Bk.D. ...)
        # 检查第一行、第一列是否以英文字母开头
        if not df.empty:
            first_val = str(df.iloc[0, 0]).strip()
            # 如果第一行第一列是 "No." 或 "No" 或 "1" (有时候 No 被洗成了 1? 不太可能，先防英文)
            # 或者检查 "Type" 列
            if is_english_start(first_val):
                logging.info(f"     🗑️ [BOC] 检测到英文表头行 (Start with '{first_val}')，已删除。")
                df = df.iloc[1:]

        # 6. 合并断行
        df = merge_hanging_rows(df, min_non_empty_cells=4)
        if df.empty: return df

        # 7. 再次清理残留 (双重保险)
        # 有时候表头没切干净，或者分页处又有表头
        c0 = df.iloc[:, 0].astype(str)
        df = df[~c0.str.contains("序号|No\\.|记账", case=False, na=False)]

        # 8. 强制统一列名
        if len(df.columns) == target_cols:
            df.columns = self.STANDARD_HEADERS
        else:
            logging.warning(f"     ⚠️ [BOC] P{page_num} 列数不匹配: {len(df.columns)} vs {target_cols}。")

        return df



