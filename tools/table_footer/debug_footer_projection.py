# tools/batch_footer_visualizer_v3.py

import pdfplumber
import pathlib
import json
import logging
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from typing import List, Dict, Any
from tqdm import tqdm
import concurrent.futures

# --- 核心配置区 ---
INPUT_ROOT = pathlib.Path(r"C:\Users\EDY\Desktop\mainProject\pdfProcess\script\processor_of_pdfplumber_v8\data\all")
OUTPUT_ROOT = pathlib.Path(r"C:\Users\EDY\Desktop\mainProject\pdfProcess\script\processor_of_pdfplumber_v8\data\all_analysis_result")

# 1. 采样精度 (Pixels per Point)
# 调高到 2.0 或 3.0 可以看到更细腻的空隙
SCAN_RESOLUTION = 2.0

# 2. 字符垂直内缩量 (Points) [关键优化]
# 如果设为 1.0，表示在计算投影时，把每个字的顶部和底部各“削去” 1个单位。
# 这能有效把紧挨着的行在视觉上分开，避免投影连成一片。
CHAR_VERTICAL_SHRINK = 1.0

# 3. 超时控制
FILE_TIMEOUT_SECONDS = 45

# 4. 是否分析所有页面 (False则只分析第一页)
ANALYZE_ALL_PAGES = True

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


class FooterAnalyzerV3:
    def __init__(self, output_dir: pathlib.Path, resolution: float = 2.0):
        self.output_dir = output_dir
        self.img_dir = output_dir / "plots"
        self.img_dir.mkdir(parents=True, exist_ok=True)
        self.resolution = resolution

    def _analyze_wrapper(self, pdf_path: pathlib.Path):
        """多进程包装器"""
        try:
            return self.process_one_pdf(pdf_path)
        except Exception as e:
            return f"Error: {e}"

    def run(self, folder_path: pathlib.Path):
        pdf_files = list(folder_path.rglob("*.pdf"))
        logging.info(f"📁 扫描到 {len(pdf_files)} 个文件，开始生成可视化报表...")
        logging.info(f"⚙️ 配置: 精度={SCAN_RESOLUTION}, 内缩={CHAR_VERTICAL_SHRINK}pt")

        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
            future_to_file = {executor.submit(self._analyze_wrapper, p): p for p in pdf_files}

            for future in tqdm(concurrent.futures.as_completed(future_to_file), total=len(pdf_files)):
                p = future_to_file[future]
                try:
                    future.result(timeout=FILE_TIMEOUT_SECONDS)
                except Exception as e:
                    logging.error(f"❌ {p.name} 处理异常: {e}")

    def process_one_pdf(self, pdf_path: pathlib.Path):
        # 局部导入防止多进程锁死
        import pdfplumber

        with pdfplumber.open(pdf_path) as pdf:
            pages_to_process = pdf.pages if ANALYZE_ALL_PAGES else pdf.pages[:1]

            for i, page in enumerate(pages_to_process):
                self._analyze_page(page, pdf_path.stem, page_num=i + 1)

    def _analyze_page(self, page, file_stem, page_num):
        height_pt = page.height
        width_pt = page.width

        # --- 1. 生成投影 Mask ---
        arr_len = int(height_pt * self.resolution)
        y_mask = np.zeros(arr_len, dtype=int)

        # 填充字符 (带内缩优化)
        # 这里我们把字符看作“阻光物”，但稍微把它们变矮一点，以便光线能穿过行距
        shrink_pixels = int(CHAR_VERTICAL_SHRINK * self.resolution)

        for char in page.chars:
            c_top = max(0, float(char['top']))
            c_bottom = min(height_pt, float(char['bottom']))

            idx_start = int(c_top * self.resolution) + shrink_pixels
            idx_end = int(c_bottom * self.resolution) - shrink_pixels

            # 如果字本身太小，就不缩了，否则消失了
            if idx_end <= idx_start:
                mid = int((c_top + c_bottom) / 2 * self.resolution)
                idx_start = mid
                idx_end = mid + 1

            idx_end = min(idx_end, arr_len)
            y_mask[idx_start:idx_end] = 1

        # 填充长横线 (不缩，线很细)
        horizontal_lines = []
        # 同时检查 lines 和 rects
        potential_lines = page.lines + [r for r in page.rects if r['height'] < 5]

        for line in potential_lines:
            # 筛选长横线 (长度 > 页宽 40%)
            if abs(line['top'] - line['bottom']) < 5 and abs(line['x1'] - line['x0']) > width_pt * 0.4:
                y_pos = float(line['top'])
                horizontal_lines.append(y_pos)

                idx = int(y_pos * self.resolution)
                if idx < arr_len:
                    y_mask[idx:min(idx + 2, arr_len)] = 1

        # --- 2. 计算 Gap 和 建议切割点 ---
        segments = self._calculate_segments(y_mask)
        cut_y = self._suggest_cut(segments, horizontal_lines, height_pt)

        # --- 3. 绘图 (包含真实图片) ---
        self._plot_result(page, y_mask, segments, horizontal_lines, cut_y, file_stem, page_num)

    def _calculate_segments(self, mask):
        segments = []
        if len(mask) == 0: return segments

        diffs = np.diff(mask)
        changes = np.where(diffs != 0)[0] + 1
        bounds = [0] + list(changes) + [len(mask)]

        for i in range(len(bounds) - 1):
            s, e = bounds[i], bounds[i + 1]
            segments.append({
                "type": "content" if mask[s] == 1 else "gap",
                "start": s / self.resolution,
                "end": e / self.resolution,
                "height": (e - s) / self.resolution
            })
        return segments

    def _suggest_cut(self, segments, lines, h):
        # 优先：下半区的最后一条长线
        bottom_lines = [y for y in lines if y > h * 0.6]
        if bottom_lines:
            return max(bottom_lines) + 2

        # 其次：下半区最大的空隙
        max_gap = 0
        cut = h
        for seg in segments:
            if seg['type'] == 'gap' and seg['start'] > h * 0.4 and seg['end'] < h - 10:
                if seg['height'] > max_gap:
                    max_gap = seg['height']
                    cut = seg['start']  # Gap开始 = 内容结束
        return cut

    def _plot_result(self, page, mask, segments, lines, cut_y, stem, p_num):
        h, w = page.height, page.width

        # 创建画布
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, int(h / 50)), gridspec_kw={'width_ratios': [2, 1]})

        # --- 左图：真实 PDF 截图 ---
        ax1.set_title(f"{stem} - P{p_num}")

        # 1. 渲染底图 (Resolution=72 也就是 1x, 150 更清晰)
        # try-except 防止缺少依赖
        try:
            pil_image = page.to_image(resolution=100).original
            # imshow extent: [left, right, bottom, top] -> 注意 Matplotlib 的 Y 轴方向
            # Matplotlib 默认原点在左上，对于图像显示是自然的
            ax1.imshow(pil_image, extent=[0, w, h, 0], aspect='auto')
        except Exception as e:
            ax1.text(w / 2, h / 2, f"Image Render Failed: {e}", ha='center')

        # 2. 叠加识别到的字符框 (半透明，用于对比)
        # 可以看到框是否比字大很多
        for char in page.chars:
            rect = patches.Rectangle(
                (char['x0'], char['top']),
                char['x1'] - char['x0'],
                char['bottom'] - char['top'],
                linewidth=0.5, edgecolor='blue', facecolor='none', alpha=0.3
            )
            ax1.add_patch(rect)

        # 3. 画线和切割建议
        for ly in lines:
            ax1.axhline(y=ly, color='red', linewidth=1, alpha=0.7)
        ax1.axhline(y=cut_y, color='purple', linewidth=2, linestyle='--', label="Cut")

        # 设置坐标轴
        ax1.set_xlim(0, w)
        ax1.set_ylim(h, 0)  # 翻转Y轴，0在上面
        ax1.legend(loc='upper right')

        # --- 右图：投影分析 ---
        ax2.set_title(f"Projection (Shrink={CHAR_VERTICAL_SHRINK})")

        # 绘制投影
        y_coords = np.arange(len(mask)) / self.resolution
        ax2.fill_betweenx(y_coords, mask, color='green', alpha=0.5)

        # 标注 Gap 数值
        for seg in segments:
            if seg['type'] == 'gap' and seg['height'] > 5:  # 只标>5的
                mid = (seg['start'] + seg['end']) / 2
                ax2.text(0.5, mid, f"{seg['height']:.1f}",
                         color='red', fontsize=7, ha='center', va='center')

        ax2.axhline(y=cut_y, color='purple', linewidth=2, linestyle='--')
        ax2.set_ylim(h, 0)
        ax2.set_xlim(0, 1.2)
        ax2.axis('off')  # 去掉右侧坐标轴边框，只看图

        # 保存
        plt.tight_layout()
        save_path = self.img_dir / f"{stem}_p{p_num}.png"
        plt.savefig(save_path, dpi=72)
        plt.close(fig)


if __name__ == "__main__":
    analyzer = FooterAnalyzerV3(OUTPUT_ROOT)
    analyzer.run(INPUT_ROOT)