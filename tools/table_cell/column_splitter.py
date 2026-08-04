# tools/column_splitter.py
import pandas as pd
import logging


def split_columns_by_header_space(df: pd.DataFrame, space_threshold: int = 5) -> pd.DataFrame:
    """
    智能拆分列：
    1. 检查表头是否包含空格。
    2. 如果包含，检查该列数据中包含空格的行数比例。
    3. 如果符合条件，将该列一分为二。
    4. 递归或循环执行，直到没有可拆分的列。

    Args:
        df: 待处理 DataFrame
        space_threshold: 该列至少有多少行包含空格，才触发拆分。
    """
    if df.empty:
        return df

    max_loops = 5  # 防止死循环
    loop_count = 0

    while loop_count < max_loops:
        split_occurred = False
        new_columns_order = []
        new_df_data = {}

        # 遍历当前所有列
        for col in df.columns:
            col_str = str(col)
            col_data = df[col].astype(str)

            # 条件1: 表头有空格
            if " " in col_str.strip():
                # 条件2: 数据列里也有很多空格
                # 统计包含空格的行数
                rows_with_space = col_data.apply(lambda x: " " in x.strip()).sum()

                if rows_with_space >= space_threshold:
                    logging.info(f"     🪓 [Splitter] 正在拆分列: '{col}' (发现 {rows_with_space} 行空格)")

                    # 执行拆分
                    # split(n=1) 只切第一刀
                    # expand=True 返回 DataFrame
                    split_df = col_data.str.split(n=1, expand=True)

                    # 生成新列名
                    # 如果表头是 "交易 金额"，切分后变成 "交易" 和 "金额"
                    parts = col_str.split(n=1)
                    if len(parts) == 2:
                        name1, name2 = parts[0], parts[1]
                    else:
                        name1, name2 = f"{col}_1", f"{col}_2"

                    # 处理 split 结果可能只有 1 列的情况 (某些行没空格)
                    if split_df.shape[1] == 1:
                        # 拆分失败（数据本身没空格，误判），保持原样
                        new_df_data[col] = df[col]
                        new_columns_order.append(col)
                    else:
                        # 成功拆分
                        new_df_data[name1] = split_df[0]
                        new_df_data[name2] = split_df[1]  # 注意: split_df[1] 可能包含 None
                        new_columns_order.append(name1)
                        new_columns_order.append(name2)
                        split_occurred = True

                    continue  # 处理下列

            # 如果不满足拆分条件，保持原样
            new_df_data[col] = df[col]
            new_columns_order.append(col)

        # 重构 DataFrame
        df = pd.DataFrame(new_df_data)
        # 保持列顺序
        df = df[new_columns_order]

        if not split_occurred:
            break  # 没有发生拆分，结束循环

        loop_count += 1

    return df