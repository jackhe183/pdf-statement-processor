# tools/cell_cleaner.py
import pandas as pd
import logging
from tools.decorators import validate_dataframe, timing_decorator


@validate_dataframe(allow_empty=True)
def clean_cell_newlines(df: pd.DataFrame) -> pd.DataFrame:
    """
    基础清洗：转字符串、去换行、去首尾空格
    """
    return df.map(lambda x: str(x).replace('\n', '').strip() if x is not None else "")


@validate_dataframe(allow_empty=True)
@timing_decorator("断行合并")
def merge_hanging_rows(df: pd.DataFrame,
                       min_non_empty_cells: int = 4) -> pd.DataFrame:
    """
    合并“挂行/空行”：
    如果某一行非空单元格数量 < 阈值，则认为它是上一行被折断的内容。
    将其内容拼接到上一行，并删除该行。
    """
    # FIXME 应该做成主干行吸附附近上下行的方式，而不是直接把断行合并到上一行，让该方法更通用。
    #  因为有时候pdfplumber把行分的很细，往往是因为单元格有两三行的文字，extract出来的excel有空行隔开每一行数据，可能这样就导致合并漏缺。

    if df.empty:
        return df

    # 步骤0: 先彻底删除全空行
    # how='all' 表示只有当这一行所有列都是 None/NaN/空字符串 时才删
    # 为了防止空字符串 "" 没被删掉，先替换一下
    df = df.replace(r'^\s*$', None, regex=True)  # 把纯空格或空字符串变成 None
    initial_len = len(df)
    df = df.dropna(how='all')
    dropped_empty_len = initial_len - len(df)

    if dropped_empty_len > 0:
        logging.info(f"     🧹 [CellCleaner] 预处理删除了 {dropped_empty_len} 个完全空行")

    # 重置索引，这对后续通过 index 访问非常重要
    df = df.reset_index(drop=True)

    if df.empty:
        return df

    # --- 步骤1: 处理挂行合并 ---
    rows_to_drop = []

    # 从第二行开始遍历
    for i in range(1, len(df)):
        row = df.iloc[i]

        # 统计非空单元格 (此时 None 已被过滤，只需判断是否为值)
        non_empty_count = row.count()

        if non_empty_count < min_non_empty_cells:
            # 判定为挂行，合并到上一行 (i-1)
            # 注意：这里假设 i-1 是有效行。如果连续多行都是挂行，逻辑会将它们依次堆叠到最上面的有效行。
            prev_idx = i - 1

            for col_idx in range(len(df.columns)):
                curr_val = str(row.iloc[col_idx]) if pd.notna(row.iloc[col_idx]) else ""
                curr_val = curr_val.strip()

                if curr_val:
                    prev_val = str(df.iloc[prev_idx, col_idx]) if pd.notna(df.iloc[prev_idx, col_idx]) else ""
                    prev_val = prev_val.strip()

                    if prev_val:
                        new_val = prev_val + " " + curr_val
                    else:
                        new_val = curr_val

                    df.iloc[prev_idx, col_idx] = new_val

            rows_to_drop.append(i)

    # 删除合并过的行
    if rows_to_drop:
        df.drop(index=rows_to_drop, inplace=True)
        logging.info(f"     🧹 [CellCleaner] 合并并删除了 {len(rows_to_drop)} 个断行")

    return df.reset_index(drop=True)