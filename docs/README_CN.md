# PDF银行对账单处理器项目说明文档

## 作者：何乃滔 2025-11-28

## 1. 项目概述

本项目是一个专门用于处理银行对账单PDF的专业框架，基于pdfplumber和pandas开发。旨在将非结构化或半结构化的PDF银行流水转换为标准化的Excel表格。

### 核心特点：
- **高度解耦架构**：将"定位(Locate)"、"裁剪(Crop)"、"提取(Extract)"、"清洗(Clean)"分为独立的生命周期步骤
- **所见即所得调试**：每页都会生成调试图（可视化识别线）和调试表（原始提取数据）
- **策略分离**：find_tables（找框）和extract_tables（读数）使用完全独立的两套配置参数
- **单页清洗**：每页独立清洗后再合并，避免跨页合并导致的列错位问题

## 2. 项目架构

```
📂 processor_of_pdfplumber_v6/
├── core/
│   └── base_pipeline.py       # 核心基类，定义了模板方法流程
├── data/
│   ├── PDFFolder_lack_lines/  # 输入：待处理的PDF文件
│   └── v8/                    # 输出：产物目录
│       ├── Debug_Images/      # 调试图：红线=识别到的表线，黄框=文字，蓝框=ROI
│       ├── Debug_Excel/       # 调试表：单页extract_tables的原始结果
│       └── Excel_Result/      # 最终结果：清洗合并后的完整Excel
├── pipelines/                 # 业务逻辑：各个银行的具体实现
│   ├── boc_pipeline.py        # 中国银行（打字机风格，去竖线）
│   ├── citic_pipeline.py      # 中信银行（无框线，纯Text策略）
│   └── tailong_pipeline.py    # 泰隆银行（Lines找框，Text读数，智能切页脚）
├── tools/                     # 工具函数
│   ├── get_pipeline_class.py  # 工厂：根据文件名分发Pipeline类
│   ├── table_header/          # 表头处理工具
│   ├── table_footer/          # 表尾处理工具
│   ├── table_cell/            # 单元格处理工具
│   └── debug/                 # 调试可视化工具
├── config.py                  # 全局路径、日志设置、调试开关
├── main.py                    # 程序入口
└── 项目说明文档.md             # 本文档
```

## 3. 核心架构逻辑

### 3.1 生命周期

对每一个PDF的每一页，都会严格依次执行以下步骤：

1. **locate_roi(page)**
   - 目的：找到表格的大致范围（ROI）
   - 工具：调用get_locate_settings()获取配置（通常是'lines'策略）
   - 输出：[x0, top, x1, bottom]坐标

2. **crop_page(page, roi)**
   - 目的：物理裁剪页面，去除页眉Logo、页脚页码干扰
   - 逻辑：子类可重写。如果locate_roi失败，可在此处通过extract_words分析文本位置进行"智能兜底裁剪"

3. **extract_tables(target_page)**
   - 目的：从裁剪后的页面提取数据
   - 工具：调用get_extract_settings()获取配置（通常是'text'策略，因为很多对账单没线）
   - 注意：这里必须和locate的配置区分开！

4. **clean_data(tables)**
   - 目的：单页清洗。将List[List[str]]转为DataFrame
   - 动作：统一表头、去除空行、去除干扰字符。必须在此步骤强制统一列名，否则后续合并会错位

5. **pd.concat (Merge)**
   - 循环结束后，基类自动将所有清洗好的单页DataFrame上下合并

### 3.2 关键设计决策

**为什么分开Locate和Extract Settings？**
- 因为泰隆银行等PDF，外框有实线（适合lines），但内部线条缺失（适合text）。如果混用一套配置，要么找不到框，要么列分不开。

**为什么需要crop_page？**
- 单纯靠clean_data去洗掉页脚的"第1页"很难，而且容易把最后一行的数字误删。不如直接在物理层面把页脚裁掉。

## 4. 使用方法

### 4.1 安装依赖

```bash
pip install pandas pdfplumber openpyxl pillow
```

### 4.2 运行程序

1. 将PDF银行对账单放入[data/PDFFolder_lack_lines/](file:///C:/Users/EDY/Desktop/mainProject/pdfProcess/script/processor_of_pdfplumber_v6/data/PDFFolder_lack_lines/)目录
2. 运行主程序：
   ```bash
   python main.py
   ```
3. 在[data/v8/](file:///C:/Users/EDY/Desktop/mainProject/pdfProcess/script/processor_of_pdfplumber_v6/data/v8)目录查看输出结果：
   - Debug_Images/：可视化调试图
   - Debug_Excel/：每页的原始提取结果
   - Excel_Result/：最终清洗合并的Excel文件

### 4.3 配置说明

修改[config.py](file:///C:/Users/EDY/Desktop/mainProject/pdfProcess/script/processor_of_pdfplumber_v6/config.py)可更改：
- 输入输出目录
- 调试设置
- 日志配置

## 5. 扩展新银行支持

以添加招商银行为例：

### 5.1 创建Pipeline文件

在[pipelines/](file:///C:/Users/EDY/Desktop/mainProject/pdfProcess/script/processor_of_pdfplumber_v6/pipelines/)目录下创建`cmb_pipeline.py`：

```python
from core.base_pipeline import BasePipeline
import pandas as pd
import pdfplumber.page
from typing import List, Optional, Dict, Any

class CMBPipeline(BasePipeline):
    def __init__(self, pdf_path):
        super().__init__(pdf_path, bank_name="cmb")

    def get_locate_settings(self, page):
        # 招行可能有线，用默认lines
        return {"vertical_strategy": "lines", "horizontal_strategy": "lines"}

    def get_extract_settings(self, page):
        # 提取时为了稳妥，也可以用text，或者混合
        return {"vertical_strategy": "text", "horizontal_strategy": "text", "snap_tolerance": 3}

    def locate_roi(self, page):
        # 实现你的找框逻辑，或者返回None全页处理
        settings = self.get_locate_settings(page)
        tables = page.find_tables(table_settings=settings)
        if tables:
            return max(tables, key=lambda t: (t.bbox[2] - t.bbox[0]) * (t.bbox[3] - t.bbox[1])).bbox
        return None

    def crop_page(self, page: pdfplumber.page.Page, roi_bbox: Optional[List[float]]) -> pdfplumber.page.Page:
        # 实现你的裁剪逻辑
        if roi_bbox:
            return page.crop(roi_bbox)
        return page

    def clean_data(self, tables: List[List[List[str]]], page_num: int) -> pd.DataFrame:
        # 实现单页清洗
        # 1. 展平列表
        # 2. 转换为DataFrame
        # 3. 修复表头（强制赋值标准列名，防止分页0,1,2问题）
        all_rows = [row for table in tables for row in table]
        if not all_rows:
            return pd.DataFrame()
        df = pd.DataFrame(all_rows)
        
        # 在此处添加你的清洗逻辑
        # ...
        
        return df
```

### 5.2 注册分发逻辑

修改[tools/get_pipeline_class.py](file:///C:/Users/EDY/Desktop/mainProject/pdfProcess/script/processor_of_pdfplumber_v6/tools/get_pipeline_class.py)：

```python
def get_pipeline_by_filename(file_path):
    name = file_path.name
    if "招商" in name:
        return CMBPipeline
    # ... 其他条件
```

## 6. 调试指南

程序运行后，检查[data/v8/](file:///C:/Users/EDY/Desktop/mainProject/pdfProcess/script/processor_of_pdfplumber_v6/data/v8)目录：

### 6.1 定位不准？
看Debug_Images：
- 红线：是pdfplumber识别到的表格线（基于settings）
- 蓝框：是locate_roi算出来的区域
- 如果红线切断了文字，调整get_extract_settings里的snap_tolerance或min_words_vertical

### 6.2 数据乱码/列错位？
看Debug_Excel：
- 这是数据清洗前的原始样子。如果这里就错了，去改Settings。如果这里是对的但结果错了，去改clean_data。

### 6.3 合并后出现0, 1, 2, 3列名？
这是因为某一页没找到表头，导致列名不匹配。
解决：在clean_data里，无论是否找到表头，最后都要强制赋值：
```python
df.columns = ["标准列名1", "标准列名2", ...]
```

## 7. 核心流程协议

BasePipeline的run方法严格遵循以下协议。任何对基类的修改不得破坏此数据流：

```python
def run(self):
    # 容器：用于存放每一页清洗后的干净数据
    all_pages_clean_data = []

    # 1. 遍历每一页 (Page Level Loop)
    for page in pdf.pages:
        
        # --- PHASE 1: 定位 (Locate) ---
        # 使用专门的"找框配置" (get_locate_settings)
        # 目的：只关心表格在哪里，不关心内容对不对
        roi_bbox = self.locate_roi(page) 

        # --- PHASE 2: 物理裁剪 (Crop) ---
        # 目的：切除页眉、页脚、Logo干扰
        # 必须返回一个新的Page对象
        target_page = self.crop_page(page, roi_bbox)

        # --- PHASE 3: 提取配置 (Settings) ---
        # 使用专门的"读数配置" (get_extract_settings)
        # 目的：只关心怎么切分列 (Text/Lines)，不关心框在哪里
        extract_settings = self.get_extract_settings(target_page)

        # --- PHASE 4: 调试产物 (Debug) ---
        # 生成可视化的图片，画出此时此刻系统看到的"线"和"字"
        if DEBUG_IMAGE: 
            save_image(target_page, extract_settings)

        # --- PHASE 5: 提取原始数据 (Extract) ---
        # 获取最原始的List[List[str]]，不做任何修改
        raw_tables = target_page.extract_tables(extract_settings)
        if DEBUG_EXCEL: 
            save_excel(raw_tables)

        # --- PHASE 6: 单页清洗 (Clean) ---
        # 输入：脏的原始列表
        # 输出：标准的DataFrame (必须统一列名！)
        # 禁止在此处进行跨页合并
        clean_df = self.clean_data(raw_tables)
        
        if not clean_df.empty:
            all_pages_clean_data.append(clean_df)

    # 2. 全文合并 (Document Level Merge)
    # --- PHASE 7: 最终合并 ---
    if all_pages_clean_data:
        # 依赖Pandas自动对齐列名
        final_df = pd.concat(all_pages_clean_data)
        save_result(final_df)
```

## 8. 开发规范

### 8.1 代码结构
- 每个银行的特殊逻辑应在各自的pipeline文件中通过重写抽象方法实现
- 复杂逻辑可在银行pipeline中进一步拆分为函数
- 所有处理都应在各银行的pipeline中完成，不应在基类中处理

### 8.2 错误处理
- 每页都在try-except块中处理，防止一个页面错误导致整个进程停止
- 实现了完善的日志记录，跟踪处理状态和错误信息

### 8.3 调试功能
- 可视化调试图精确显示pdfplumber如何看待文档
- 保存每页的原始提取结果，便于调试分析
- 全面的日志跟踪处理流程和问题定位

本文档为PDF银行对账单处理器提供了全面的使用、理解和扩展指南。模块化架构使得添加新银行支持变得简单，同时保持了处理逻辑的一致性。