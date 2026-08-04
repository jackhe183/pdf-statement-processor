# tools/header_remover.py
import pandas as pd
import logging


def remove_header_by_keyword(df: pd.DataFrame,
                             page_num: int,
                             keyword: str = "摘要") -> pd.DataFrame:
    """
    表头剔除器：
    1. Page 1: 找到关键词行，将其设为 DataFrame 的 columns，并保留下方数据。
    2. Page >1: 找到关键词行，直接删除该行及其上方所有内容，只保留纯数据。
    """
    if df.empty:
        return df

    # 1. 寻找关键词所在的行索引
    header_idx = -1
    for i, row in df.iterrows():
        # 将行转为字符串查找关键词
        row_str = "".join([str(x) for x in row if x])
        if keyword in row_str:
            header_idx = i
            break

    # 2. 根据页码分别处理
    if page_num == 1:
        # --- 第一页：必须确立表头 ---
        if header_idx != -1:
            logging.info(f"     ✅ [HeaderRemover] 第1页：找到表头行 (Index {header_idx})，已应用为列名。")
            df.columns = df.iloc[header_idx]
            df = df.iloc[header_idx + 1:]
        else:
            logging.warning(f"     ⚠️ [HeaderRemover] 第1页：未找到包含 '{keyword}' 的表头行，列名可能不正确。")

    else:
        # --- 后续页：剔除重复表头 ---
        if header_idx != -1:
            logging.info(f"     ✂️ [HeaderRemover] 第{page_num}页：检测到重复表头 (Index {header_idx})，已剔除。")
            # 直接切掉表头及以上的部分
            df = df.iloc[header_idx + 1:]

            # [重要] 重置列名为默认数字，防止残留旧列名干扰后续的强制重命名
            # 这一步是为了让 Pipeline 的 STANDARD_HEADERS 逻辑能顺利接手
            df.columns = range(df.shape[1])
        else:
            # 如果没找到表头，说明这一页全是纯数据（或是上一页的延伸），保持原样
            pass

    # 重置索引，保证整洁
    return df.reset_index(drop=True)