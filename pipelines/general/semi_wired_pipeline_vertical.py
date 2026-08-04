
from typing import Dict, Any
import pdfplumber.page
from core.base_pipeline import BasePipeline

class SemiWiredPipelineHorizon(BasePipeline):
    def __init__(self, pdf_path):
        # 在这里告诉父类：这个银行找表头要用 "摘要" 这个词
        super().__init__(pdf_path, bank_name="semi_wired_bank")

    def get_extract_settings(self, page: pdfplumber.page.Page) -> Dict[str, Any]:
        """
        因为 calculate_crop_bbox 和 clean_data 直接复用 BasePipeline 的默认逻辑即可。
        """
        return {
            "vertical_strategy": "lines",
            "horizontal_strategy": "text",
            "snap_tolerance": 3,
            "min_words_vertical": 3,
            "explicit_vertical_lines": [0, page.width],
            "join_tolerance": 3,

        }