# PDF Bank Statement Processor Documentation

## Author: Jack He 2025-11-28

## 1. Project Overview

This project is a specialized framework for processing bank statement PDFs using pdfplumber and pandas. It's designed to convert unstructured or semi-structured PDF bank statements into standardized Excel tables.

### Key Features:
- **Highly Decoupled Architecture**: Separates "Locate", "Crop", "Extract", "Clean" into independent lifecycle steps
- **Visual Debugging**: Each page generates Debug Images (visual recognition lines) and Debug Excel (raw extraction data)
- **Strategy Separation**: Uses completely independent configuration parameters for find_tables (finding boxes) and extract_tables (reading data)
- **Single Page Cleaning**: Each page is cleaned independently before final merging to avoid cross-page alignment issues

## 2. Project Architecture

```
📂 processor_of_pdfplumber_v6/
├── core/
│   └── base_pipeline.py       # Core base class defining the Template Method process
├── data/
│   ├── PDFFolder_lack_lines/  # Input: PDF files to process
│   └── v8/                    # Output: results directory
│       ├── Debug_Images/      # Debug images: red lines=recognized table lines, yellow boxes=text, blue boxes=ROI
│       ├── Debug_Excel/       # Debug tables: raw extract_tables results for each page
│       └── Excel_Result/      # Final result: cleaned and merged Excel files
├── pipelines/                 # Business logic: specific implementations for each bank
│   ├── boc_pipeline.py        # Bank of China (typewriter style, remove vertical lines)
│   ├── citic_pipeline.py      # CITIC Bank (no frame lines, pure Text strategy)
│   └── tailong_pipeline.py    # Tailong Bank (Lines for finding boxes, Text for reading, intelligent footer cutting)
├── tools/                     # Utility functions
│   ├── get_pipeline_class.py  # Factory: dispatches Pipeline class based on filename
│   ├── table_header/          # Header processing utilities
│   ├── table_footer/          # Footer processing utilities
│   ├── table_cell/            # Cell processing utilities
│   └── debug/                 # Debug visualization tools
├── config.py                  # Global paths, logging settings, debug switches
├── main.py                    # Program entry point
└── PROJECT_DOCUMENTATION.md   # This documentation file
```

## 3. Core Architecture Logic

### 3.1 Lifecycle

For each page of every PDF, the system strictly executes the following steps:

1. **locate_roi(page)**
   - Purpose: Find the approximate table area (ROI)
   - Tool: Calls get_locate_settings() to get configuration (usually 'lines' strategy)
   - Output: [x0, top, x1, bottom] coordinates

2. **crop_page(page, roi)**
   - Purpose: Physically crop the page to remove header logos and footer page numbers
   - Logic: Subclasses can override this. If locate_roi fails, this can perform "intelligent fallback cropping" by analyzing text positions through extract_words

3. **extract_tables(target_page)**
   - Purpose: Extract data from the cropped page
   - Tool: Calls get_extract_settings() to get configuration (usually 'text' strategy since many statements have no lines)
   - Note: This must be distinguished from locate settings!

4. **clean_data(tables)**
   - Purpose: Single page cleaning. Converts List[List[str]] to DataFrame
   - Actions: Standardize headers, remove empty rows, remove interference characters. Must enforce column names here to prevent misalignment in subsequent merging

5. **pd.concat (Merge)**
   - After the loop ends, the base class automatically merges all cleaned single-page DataFrames vertically

### 3.2 Key Design Decisions

**Why separate Locate and Extract Settings?**
- Because banks like Tailong have solid outer frames (suitable for lines) but missing inner lines (suitable for text). Mixing configurations would either fail to find boxes or fail to separate columns.

**Why is crop_page needed?**
- It's easier to physically crop the footer than to clean it in clean_data, and it avoids accidentally deleting the last row of numbers.

## 4. How to Use

### 4.1 Installation

```bash
pip install pandas pdfplumber openpyxl pillow
```

### 4.2 Running the Program

1. Place your PDF bank statements in the [data/PDFFolder_lack_lines/](file:///C:/Users/EDY/Desktop/mainProject/pdfProcess/script/processor_of_pdfplumber_v6/data/PDFFolder_lack_lines) directory
2. Run the main script:
   ```bash
   python main.py
   ```
3. Check the output in the [data/v8/](file:///C:/Users/EDY/Desktop/mainProject/pdfProcess/script/processor_of_pdfplumber_v6/data/v8) directory:
   - Debug_Images/: Visual debugging images
   - Debug_Excel/: Raw extraction results for each page
   - Excel_Result/: Final cleaned and merged Excel files

### 4.3 Configuration

Modify [config.py](file:///C:/Users/EDY/Desktop/mainProject/pdfProcess/script/processor_of_pdfplumber_v6/config.py) to change:
- Input/output directories
- Debug settings
- Logging configuration

## 5. Extending for New Banks

To add support for a new bank (e.g., China Merchants Bank):

### 5.1 Create Pipeline File

Create `cmb_pipeline.py` in the [pipelines/](file:///C:/Users/EDY/Desktop/mainProject/pdfProcess/script/processor_of_pdfplumber_v6/pipelines) directory:

```python
from core.base_pipeline import BasePipeline
import pandas as pd
import pdfplumber.page
from typing import List, Optional, Dict, Any

class CMBPipeline(BasePipeline):
    def __init__(self, pdf_path):
        super().__init__(pdf_path, bank_name="cmb")

    def get_locate_settings(self, page):
        # CMB may have lines, use default lines
        return {"vertical_strategy": "lines", "horizontal_strategy": "lines"}

    def get_extract_settings(self, page):
        # For extraction, use text for safety, or mix strategies
        return {"vertical_strategy": "text", "horizontal_strategy": "text", "snap_tolerance": 3}

    def locate_roi(self, page):
        # Implement your box-finding logic, or return None for full-page processing
        settings = self.get_locate_settings(page)
        tables = page.find_tables(table_settings=settings)
        if tables:
            return max(tables, key=lambda t: (t.bbox[2] - t.bbox[0]) * (t.bbox[3] - t.bbox[1])).bbox
        return None

    def crop_page(self, page: pdfplumber.page.Page, roi_bbox: Optional[List[float]]) -> pdfplumber.page.Page:
        # Implement your cropping logic
        if roi_bbox:
            return page.crop(roi_bbox)
        return page

    def clean_data(self, tables: List[List[List[str]]], page_num: int) -> pd.DataFrame:
        # Implement single-page cleaning
        # 1. Flatten list
        # 2. Convert to DataFrame
        # 3. Fix Headers (enforce standard column names to prevent 0,1,2 column name issues)
        all_rows = [row for table in tables for row in table]
        if not all_rows:
            return pd.DataFrame()
        df = pd.DataFrame(all_rows)
        
        # Add your cleaning logic here
        # ...
        
        return df
```

### 5.2 Register Dispatch Logic

Modify [tools/get_pipeline_class.py](file:///C:/Users/EDY/Desktop/mainProject/pdfProcess/script/processor_of_pdfplumber_v6/tools/get_pipeline_class.py):

```python
def get_pipeline_by_filename(file_path):
    name = file_path.name
    if "招商" in name:
        return CMBPipeline
    # ... other conditions
```

## 6. Debugging Guide

After running the program, check the [data/v8/](file:///C:/Users/EDY/Desktop/mainProject/pdfProcess/script/processor_of_pdfplumber_v6/data/v8) directory:

### 6.1 Poor Location?
Check Debug_Images:
- Red lines: Table lines recognized by pdfplumber (based on settings)
- Blue box: Area calculated by locate_roi
- If red lines cut through text, adjust snap_tolerance or min_words_vertical in get_extract_settings

### 6.2 Garbled Data/Column Misalignment?
Check Debug_Excel:
- This is the raw data before cleaning. If it's wrong here, adjust Settings. If it's correct here but wrong in the result, adjust clean_data.

### 6.3 Merged Result Shows 0, 1, 2, 3 Column Names?
This happens when a page doesn't find the header, causing column name mismatches.
Solution: In clean_data, enforce column names regardless of whether the header is found:
```python
df.columns = ["Standard Column 1", "Standard Column 2", ...]
```

## 7. Core Pipeline Protocol

The BasePipeline's run method strictly follows this protocol. Any modifications to the base class must not break this data flow:

```python
def run(self):
    # Container: stores cleaned data from each page
    all_pages_clean_data = []

    # 1. Iterate through each page (Page Level Loop)
    for page in pdf.pages:
        
        # --- PHASE 1: Locate ---
        # Use dedicated "box-finding configuration" (get_locate_settings)
        # Purpose: Only care where the table is, not the content
        roi_bbox = self.locate_roi(page) 

        # --- PHASE 2: Physical Crop ---
        # Purpose: Remove header, footer, logo interference
        # Must return a new Page object
        target_page = self.crop_page(page, roi_bbox)

        # --- PHASE 3: Extract Configuration ---
        # Use dedicated "data reading configuration" (get_extract_settings)
        # Purpose: Only care how to separate columns (Text/Lines), not where the boxes are
        extract_settings = self.get_extract_settings(target_page)

        # --- PHASE 4: Debug Output ---
        # Generate visual images showing the lines and text the system sees at this moment
        if DEBUG_IMAGE: 
            save_image(target_page, extract_settings)

        # --- PHASE 5: Extract Raw Data ---
        # Get the most raw List[List[str]], without any modifications
        raw_tables = target_page.extract_tables(extract_settings)
        if DEBUG_EXCEL: 
            save_excel(raw_tables)

        # --- PHASE 6: Single Page Cleaning ---
        # Input: Dirty raw list
        # Output: Standard DataFrame (must standardize column names!)
        # Prohibited: Perform cross-page merging here
        clean_df = self.clean_data(raw_tables)
        
        if not clean_df.empty:
            all_pages_clean_data.append(clean_df)

    # 2. Full Document Merge (Document Level Merge)
    # --- PHASE 7: Final Merge ---
    if all_pages_clean_data:
        # Rely on Pandas to automatically align column names
        final_df = pd.concat(all_pages_clean_data)
        save_result(final_df)
```

## 8. Development Standards

### 8.1 Code Structure
- Each bank's specific logic should be implemented in its own pipeline file by overriding abstract methods
- Complex logic can be further broken down into functions within the bank's pipeline
- All processing should happen within each bank's pipeline, not in the base class

### 8.2 Error Handling
- Each page is processed in a try-except block to prevent one page error from stopping the entire process
- Proper logging is implemented to track processing status and errors

### 8.3 Debugging Features
- Visual debugging images show exactly how pdfplumber sees the document
- Raw extraction results are saved for each page to facilitate debugging
- Comprehensive logging tracks the processing flow and issues

This documentation provides a comprehensive guide for understanding, using, and extending the PDF Bank Statement Processor. The modular architecture makes it easy to add support for new banks while maintaining consistency in processing logic.