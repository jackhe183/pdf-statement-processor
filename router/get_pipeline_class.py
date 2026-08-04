# tools/get_pipeline_class.py
import pathlib
from typing import Type
from core.base_pipeline import BasePipeline
from pipelines.specific.boc_pipeline import BOCPipeline
from pipelines.general.wired_pipeline import WiredPipeline
from pipelines.general.semi_wired_pipeline_horizon import SemiWiredPipelineHorizon
from pipelines.general.wireless_pipeline import WirelessPipeline
from pipelines.general.semi_wired_pipeline_vertical import SemiWiredPipelineVertical

# 技术债，使用写死的逻辑临时解决，后期需要改成动态获取，除非后端那边可以获取银行名称
def get_pipeline_class(file_path: pathlib.Path) -> Type[BasePipeline]:
    name = file_path.name.lower()
    if "中国银行" in name:
        return BOCPipeline
    elif "建设" in name or "浙江德清" in name:
        return SemiWiredPipelineVertical
    elif "中信银行" in name or "招商" in name:
        return SemiWiredPipelineHorizon
    elif "泰隆" in name or "民生" in name or "平安" in name or "深圳福田" in name:
        return WirelessPipeline
    elif "银行" in name:
        return WiredPipeline
    else:
        raise ValueError("无法从文件名获取银行名称，请检查该文件是否为银行对账单。")