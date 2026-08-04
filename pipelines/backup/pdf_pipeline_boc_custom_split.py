# pdf_pipeline_boc_final.py
# 专用于：中国银行对账单 (最终优化版)
# 功能升级：
# 1. [新增] 自动删除连续重复10次以上的垃圾字符 (如 "----------")
# 2. [保留] 强制 "|" 拆分、表头定位、序号合并、换行符清洗

import pdfplumber
import pathlib
import pandas as pd
import logging
import re

# --- 配置区 ---
PDF_PATH = pathlib.Path(r"/pdfProcess/data/PDFFolder/中国银行_0120.pdf")
OUTPUT_EXCEL = pathlib.Path("BOC_Result_Final.xlsx")


class BOCPipelineFinal:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.pdf = None

    def __enter__(self):
        self.pdf = pdfplumber.open(self.pdf_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.pdf:
            self.pdf.close()

    def clean_repetitive_string(self, text, threshold=10):
        """
        清洗逻辑：如果某个字符连续重复出现 threshold 次以上，则删除该字符串。
        例如: "----------" (10个-) -> ""
        注意：这可能会误伤像 '1111111111' 这样的长数字，
        但银行金额通常不会有10个连续相同的数字(100亿是1000...)，故风险较低。
        """
        if not isinstance(text, str):
            return text

        # 正则解释：
        # (.)      -> 捕获任意一个字符
        # \1       -> 引用第一个捕获组（即刚才那个字符）
        # {N,}     -> 重复 N 次以上
        # threshold-1 因为第一个字符已经被 (.) 捕获了
        pattern = r'(.)\1{' + str(threshold - 1) + r',}'

        # 将匹配到的重复串替换为空
        return re.sub(pattern, '', text)

    def run(self):
        all_data = []
        print(f"🚀 开始处理: {self.pdf_path.name}")

        for i, page in enumerate(self.pdf.pages):
            print(f"\n📄 第 {i + 1} 页:")

            # 1. 定位
            table_bbox = self.stage_1_locate_table_area(page)
            if not table_bbox:
                print("   ⚠️ 未找到表格区域，跳过。")
                continue

            # 2. 裁剪
            cropped_page = self.stage_2_crop_area(page, table_bbox)

            # 3. 提取
            raw_table = self.stage_3_extract_data(cropped_page)

            if raw_table:
                # 4. 深度清洗 (新增了去重逻辑)
                df = self.stage_4_split_and_clean(raw_table)

                if not df.empty:
                    all_data.append(df)
                    print(f"   ✅ 处理完成: {len(df)} 条记录")
                else:
                    print("   ⚠️ 数据清洗后为空")

        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)
            final_df = final_df.dropna(how='all')
            final_df.to_excel(OUTPUT_EXCEL, index=False)
            print(f"\n🎉 全部完成！结果已保存至: {OUTPUT_EXCEL}")
        else:
            print("\n❌ 未提取到任何有效数据。")

    # --- 阶段实现 ---

    def stage_1_locate_table_area(self, page):
        LOCATE_SETTINGS = {
            "vertical_strategy": "text",
            "horizontal_strategy": "text",
            "snap_tolerance": 5,
        }
        tables = page.find_tables(table_settings=LOCATE_SETTINGS)
        if not tables: return None
        return max(tables, key=lambda t: (t.bbox[2] - t.bbox[0]) * (t.bbox[3] - t.bbox[1])).bbox

    def stage_2_crop_area(self, page, bbox):
        return page.crop(bbox)

    def stage_3_extract_data(self, cropped_page):
        EXTRACT_SETTINGS = {
            "vertical_strategy": "text",
            "horizontal_strategy": "text",
            "text_tolerance": 1,
            "intersection_tolerance": 5
        }
        return cropped_page.extract_table(table_settings=EXTRACT_SETTINGS)

    def stage_4_split_and_clean(self, raw_table):
        # --- A. 预处理：强制按 "|" 拆分 ---
        splitted_table = []

        for row in raw_table:
            row_str = " ".join([str(x).strip() for x in row if x])

            if row_str.count('|') >= 5:
                parts = row_str.split('|')
                # 去除两端空白
                parts = [p.strip() for p in parts]

                # 去除首尾空元素
                if parts and parts[0] == '': parts.pop(0)
                if parts and parts[-1] == '': parts.pop()

                splitted_table.append(parts)
            else:
                clean_row = [str(x).strip() for x in row if x]
                if clean_row:
                    splitted_table.append(clean_row)

        if not splitted_table:
            return pd.DataFrame()

        # --- B. 寻找表头 ---
        header_idx = -1
        for idx, row in enumerate(splitted_table):
            row_str = "".join(row)
            if "摘要" in row_str and "序号" in row_str:
                header_idx = idx
                break

        if header_idx == -1: return pd.DataFrame()

        headers = splitted_table[header_idx]
        data_rows = splitted_table[header_idx + 1:]

        try:
            seq_col_idx = next(i for i, h in enumerate(headers) if "序号" in h)
        except StopIteration:
            seq_col_idx = 0

            # --- C. 基于序号的合并逻辑 ---
        merged_rows = []
        current_record = None
        num_columns = len(headers)

        for row in data_rows:
            # 1. 列数归一化
            if len(row) < num_columns: row += [''] * (num_columns - len(row))
            if len(row) > num_columns: row = row[:num_columns]

            # 2. 【新增】清洗单元格内的连续重复字符
            #    这里调用 clean_repetitive_string，把 "----------" 这种变成 ""
            row = [self.clean_repetitive_string(cell, threshold=10) for cell in row]

            # 3. 判断新行逻辑
            seq_val = row[seq_col_idx]
            is_new_record = False
            if seq_val.isdigit():
                is_new_record = True
            elif seq_val == "":
                is_new_record = False
            else:
                is_new_record = True if current_record is None else False

            # 4. 合并或追加
            if is_new_record:
                if current_record:
                    merged_rows.append(current_record)
                current_record = row
            else:
                if current_record:
                    for i in range(len(current_record)):
                        if i < len(row) and row[i]:
                            current_record[i] += " " + row[i]

        if current_record:
            merged_rows.append(current_record)

        # --- D. 生成 DataFrame ---
        df = pd.DataFrame(merged_rows, columns=headers)

        # 全局清洗：去除 '/' 和 '\n'
        df = df.replace(r'[\n/]', '', regex=True)

        return df


# --- 执行入口 ---
if __name__ == "__main__":
    if PDF_PATH.exists():
        with BOCPipelineFinal(PDF_PATH) as pipeline:
            pipeline.run()
    else:
        print(f"文件不存在: {PDF_PATH}")