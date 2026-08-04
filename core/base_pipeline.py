# core/base_pipeline.py

# --- 标准库导入 ---
import pathlib
import logging
from typing import List, Optional, Any, Dict, Tuple
from abc import ABC, abstractmethod

# --- 第三方库导入 ---
import pdfplumber
import pdfplumber.page
import pandas as pd

# --- 本地应用/库导入 ---
import config
from tools.debug.image_debug_visualizer import save_debug_image
from tools.decorators import timing_decorator, safe_execute, debug_save
from tools.pdf_watermark_remover import remove_pdf_watermarks
from tools.table_header.header_remover import remove_header_by_keyword
from tools.table_header.header_finder import find_header_position
from tools.table_footer.footer_finder import find_table_bottom_comprehensive
from tools.table_cell.cell_cleaner import merge_hanging_rows

class BasePipeline(ABC):
    def __init__(self, pdf_path: pathlib.Path, bank_name: str, header_keywords: List[str] = None):
        """
        Args:
            header_keywords: 用于定位表头和清洗数据的关键字列表。默认 ["摘要", "交易日期"]
        """
        self.pdf_path = pdf_path
        self.bank_name = bank_name
        # 默认关键字，子类可以通过 super().__init__ 覆盖
        self.header_keywords = ["摘要"]

        config.DEBUG_IMG_DIR.mkdir(parents=True, exist_ok=True)
        config.DEBUG_EXCEL_DIR.mkdir(parents=True, exist_ok=True)
        config.RESULT_DIR.mkdir(parents=True, exist_ok=True)

    @timing_decorator("整体处理流程")
    def run(self):
        logging.info(f"🚀 开始处理 [{self.bank_name}]: {self.pdf_path.name}")
        all_pages_clean_data = []

        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_num = i + 1
                    logging.info(f"  -> 处理第 {page_num} 页...")

                    try:
                        # Step 0: 预处理 - 去水印
                        # 这一步至关重要，返回一个去除了红章、蓝色Logo干扰的干净页面
                        clean_page = remove_pdf_watermarks(page)

                        # Step 1: 定位 (Locate)
                        # 子类负责计算有效内容的坐标框 (x0, top, x1, bottom)
                        bbox = self.calculate_crop_bbox(clean_page)

                        # Step 2: 裁剪 (Crop)
                        # 基类统一执行裁切。如果子类没算出bbox(None)，则默认处理全页
                        if bbox:
                            target_page = clean_page.crop(bbox)
                            logging.info(f"     ✂️ 执行裁切: Top={bbox[1]:.2f}, Bottom={bbox[3]:.2f}")
                        else:
                            target_page = clean_page
                            logging.warning("     ⚠️ 未计算出有效裁切区域，使用全页处理。")

                        # Step 3: 获取提取参数 (Settings)
                        # 此时传入的是已经裁切好的 target_page，子类可以根据它的特征动态调整参数
                        extract_settings = self.get_extract_settings(target_page)

                        # Step 4: 调试输出图片 (Debug Image)
                        # 传入原始 page (带水印) 和 target_page (去水印+裁切后) 进行对比
                        self._save_debug_image(page, target_page, extract_settings, page_num)

                        # Step 5: 提取表格 (Extract)
                        tables = target_page.extract_tables(table_settings=extract_settings)

                        # Step 6: 调试输出表格 (Debug Excel)
                        # 保存未经清洗的原始提取结果，便于排查提取层面的问题
                        self._save_debug_excel(tables, page_num)

                        if not tables:
                            logging.warning(f"     ⚠️ 第 {page_num} 页未检测到表格。")
                            continue

                        # Step 7: 数据清洗 (Clean)
                        # 子类负责去表头、合并行等业务逻辑
                        cleaned_page_df = self.clean_data(tables, page_num)

                        if not cleaned_page_df.empty:
                            logging.info(
                                f"     ✅ 第 {page_num} 页清洗完成，行数: {len(cleaned_page_df)}，列数: {len(cleaned_page_df.columns)}")
                            all_pages_clean_data.append(cleaned_page_df)
                        else:
                            logging.info(f"     ⚪ 第 {page_num} 页清洗后为空。")

                    except Exception as e_page:
                        logging.error(f"     ❌ 第 {page_num} 页处理失败: {e_page}", exc_info=True)

            # Step 8: 智能合并与输出 (Smart Merge & Output)
            if all_pages_clean_data:
                self._merge_and_save(all_pages_clean_data)
            else:
                logging.warning(f"⚠️ 文件 {self.pdf_path.name} 未提取到任何有效数据。")

        except Exception as e:
            logging.error(f"❌ 文件级错误: {e}", exc_info=True)

    # --- 抽象接口定义 (由子类实现) ---

    @safe_execute(default_return=None)
    def calculate_crop_bbox(self, page: pdfplumber.page.Page) -> Optional[Tuple[float, float, float, float]]:
        """
        【默认定位逻辑】X轴全宽 + Y轴智能切割
        大多数银行都适用此逻辑。如果不适用，子类可以直接重写此方法。
        """
        # 1. 找头 (Top)
        top = find_header_position(page=page, roi_bbox=None, keywords=self.header_keywords)

        # 2. 找尾 (Bottom)
        bottom = find_table_bottom_comprehensive(
            page=page,
            header_top=top,
            roi_bbox=None,
            sparsity_threshold=20
        )

        # 3. 检查
        if bottom <= top + 10:
            logging.warning(f"     ⚠️ 计算出的区域无效 (Top={top:.2f}, Bottom={bottom:.2f})，跳过此页。")
            return None

        logging.info(f" 📐 坐标计算完成 (Base): Top={top:.2f}, Bottom={bottom:.2f}")
        return (0, top, page.width, bottom)

    @timing_decorator("数据清洗")
    @safe_execute(default_return=pd.DataFrame())
    def clean_data(self, tables: List[List[List[str]]], page_num: int) -> pd.DataFrame:
        """
        【默认清洗逻辑】
        1. 展平表格
        2. 去除重复表头 (基于 header_keywords 的第一个词)
        3. 合并悬挂行
        """
        all_rows = [row for table in tables for row in table]
        if not all_rows: return pd.DataFrame()
        df = pd.DataFrame(all_rows)

        # 使用初始化时定义的第一个关键字来去重表头
        keyword = self.header_keywords[0]
        df = remove_header_by_keyword(df=df, page_num=page_num, keyword=keyword)

        # 默认合并悬挂行
        df = merge_hanging_rows(df=df, min_non_empty_cells=4)

        return df

    # 仍要求子类重写提取逻辑
    @abstractmethod
    def get_extract_settings(self, page: pdfplumber.page.Page) -> Dict[str, Any]:
        """
        定义 pdfplumber 的表格提取参数 (vertical_strategy 等)。
        """
        pass

    # --- 内部辅助方法 ---

    def _merge_and_save(self, data_list: List[pd.DataFrame]):
        """合并所有页面的数据并保存"""
        logging.info(f"  -> 开始合并 {len(data_list)} 个页面的数据...")

        # 简单对齐策略：以第一页为准
        base_df = data_list[0]
        standard_columns = base_df.columns
        standard_col_count = len(standard_columns)

        aligned_pages = [base_df]

        for idx, df in enumerate(data_list[1:], start=2):
            if len(df.columns) == standard_col_count:
                df.columns = standard_columns
                aligned_pages.append(df)
            else:
                logging.warning(f"     ⚠️ P{idx} 列数不一致，强行合并可能导致错位。")
                aligned_pages.append(df)

        final_df = pd.concat(aligned_pages, ignore_index=True)
        self.save_final_excel(final_df)

    def save_final_excel(self, df: pd.DataFrame):
        filename = f"{self.pdf_path.stem}.xlsx"
        output_path = config.RESULT_DIR / filename
        df.to_excel(output_path, index=False)
        logging.info(f"✅ 最终合并结果已保存: {output_path.name}")

    @debug_save("image")
    def _save_debug_image(self, original_page, target_page, settings, page_num):
        filename = f"{self.pdf_path.stem}_P{page_num}.png"
        output_path = config.DEBUG_IMG_DIR / filename
        save_debug_image(original_page, target_page, settings, output_path)

    @debug_save("excel")
    def _save_debug_excel(self, tables, page_num):
        filename = f"{self.pdf_path.stem}_P{page_num}.xlsx"
        output_path = config.DEBUG_EXCEL_DIR / filename
        all_rows = []
        for t in tables:
            all_rows.extend(t)
            all_rows.append([])
        pd.DataFrame(all_rows).to_excel(output_path, index=False, header=False)
        logging.info(f"     📊 调试Excel已保存: {output_path.name}")