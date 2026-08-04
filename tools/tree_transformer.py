# tree_manager.py
# 用途：项目结构管理工具 (双向转换)
# 模式：
#   1. view: [磁盘 -> 文本] 扫描当前文件夹，生成树状结构文本
#   2. make: [文本 -> 磁盘] 根据下方的 TREE_STRUCTURE_TEXT，在磁盘创建文件夹和文件

import pathlib
import os
import re

# ================= 配置区 =================

# --- 全局配置 ---
# 脚本工作的根目录 (默认当前目录)
ROOT_DIR = pathlib.Path(r'C:\Users\EDY\Desktop\mainProject\pdfProcess\script\processor_of_pdfplumber_v6')

# 当前模式: 'view' 或 'make'
MODE = 'view'

# --- [View 模式] 配置 ---
# 完全忽略的目录 (既不显示也不进入)
IGNORE_DIRS = {'.git', '.idea', '__pycache__', '.venv', '.vscode', 'Debug_Images'}
# 只显示目录结构，不显示文件的目录
FOLDERS_ONLY_DIRS = {'data'}

# --- [Make 模式] 配置 ---
# 将 view 模式生成的文本粘贴到这里，用于重建结构
TREE_STRUCTURE_TEXT = r"""
📂 processor_of_pdfplumber
├── config.py
├── core
│   ├── __init__.py
│   └── base_pipeline.py
├── data
│   ├── boc
│   └── PDFFolder
├── main.py
├── pipelines
│   ├── __init__.py
│   └── boc_pipeline.py
├── utils
│   ├── __init__.py
│   └── common.py
"""


# =========================================

class TreeManager:
    def __init__(self, root: pathlib.Path):
        self.root = root

    # ---------------------------------------------------------
    # 1. View 模式: 磁盘 -> 文本
    # ---------------------------------------------------------
    def view(self):
        if not self.root.exists():
            print(f"❌ 路径不存在: {self.root}")
            return

        print(f"📂 {self.root.resolve().name}")
        self._print_tree_recursive(self.root)

    def _print_tree_recursive(self, directory: pathlib.Path, prefix='', parent_is_folder_only=False):
        try:
            # 过滤掉忽略的目录
            all_items = sorted(
                [p for p in directory.iterdir() if p.name not in IGNORE_DIRS],
                key=lambda x: (not x.is_dir(), x.name.lower())  # 文件夹排前面
            )
        except PermissionError:
            return

        # 判断当前是否只显示目录
        current_is_folder_only = parent_is_folder_only or (directory.name in FOLDERS_ONLY_DIRS)

        # 筛选
        display_items = []
        for p in all_items:
            if p.is_dir():
                display_items.append(p)
            elif not current_is_folder_only:  # 如果是文件且没开启“只看目录”
                display_items.append(p)

        # 打印
        count = len(display_items)
        for index, path in enumerate(display_items):
            is_last = (index == count - 1)
            connector = '└── ' if is_last else '├── '

            print(f"{prefix}{connector}{path.name}")

            if path.is_dir():
                extension = '    ' if is_last else '│   '
                self._print_tree_recursive(path, prefix + extension, current_is_folder_only)

    # ---------------------------------------------------------
    # 2. Make 模式: 文本 -> 磁盘
    # ---------------------------------------------------------
    def make(self):
        print(f"🚀 开始在 {self.root} 构建结构...")

        # 1. 解析文本行
        lines = [line for line in TREE_STRUCTURE_TEXT.split('\n') if line.strip()]
        if not lines:
            print("⚠️ TREE_STRUCTURE_TEXT 为空")
            return

        # 路径栈：[(indent_level, path_object)]
        # 初始化栈，假设第一行是根或者直接开始子项
        stack = []

        # 检查第一行是否是根目录标记 (📂)
        first_line = lines[0]
        if '📂' in first_line:
            # 如果第一行是根名字，我们不创建它，而是作为后续的基准
            # 也可以选择忽略，直接在 ROOT_DIR 下创建
            lines = lines[1:]

            # 初始基准：Indent -1 (代表 ROOT_DIR 本身)
        stack.append((-1, self.root))

        for line in lines:
            # 解析缩进层级和文件名
            indent_level, name, is_last_symbol = self._parse_line(line)
            if not name: continue

            # 调整栈：弹出比当前层级深或同级的父节点，找到当前节点的直接父级
            while stack and stack[-1][0] >= indent_level:
                stack.pop()

            parent_path = stack[-1][1]
            current_path = parent_path / name

            # 判断是文件还是文件夹
            # 逻辑：如果有后缀名(如 .py) 或者是 __init__ 则视为文件
            # 否则视为文件夹 (这只是简单的启发式规则，可以根据需要修改)
            is_file = '.' in name and not name.startswith('.')  # 简单的后缀判断
            # 特殊处理：__init__ 没后缀也是文件，.gitignore 开头有点也是文件
            if name == '__init__' or name.startswith('.'):
                is_file = True
            # 特殊处理：如果名字里没有点，但也想做成文件？通常代码项目文件夹没有点，文件有后缀。
            # 只要不含后缀，默认为文件夹
            if not is_file:
                self._create_dir(current_path)
                stack.append((indent_level, current_path))  # 只有文件夹才入栈作为父级
            else:
                self._create_file(current_path)

        print("✅ 结构构建完成。")

    def _parse_line(self, line):
        """解析树状图的一行，返回 (缩进层级, 名称)"""
        # 移除所有树状符号，只保留缩进和名字
        # 典型的符号：│   ├──    └──
        # 每一个层级通常占 4 个字符宽度

        # 正则匹配前缀符号
        match = re.match(r'^([│\s├└─]*)', line)
        prefix = match.group(1) if match else ""
        name = line[len(prefix):].strip()

        # 计算层级：前缀长度 / 4 (标准的 tree 输出通常是 4空格宽)
        # 但为了容错，我们计算 '│' ' ' 的数量
        # 简单粗暴法：直接看前缀长度
        indent_level = len(prefix) // 4

        return indent_level, name, '└──' in prefix

    def _create_dir(self, path: pathlib.Path):
        if not path.exists():
            path.mkdir(parents=True)
            print(f"   [DIR ] 创建: {path.name}")
        else:
            # print(f"   [SKIP] 存在: {path.name}")
            pass

    def _create_file(self, path: pathlib.Path):
        if not path.exists():
            path.touch()
            print(f"   [FILE] 创建: {path.name}")
        else:
            # print(f"   [SKIP] 存在: {path.name}")
            pass


if __name__ == "__main__":
    manager = TreeManager(ROOT_DIR)

    if MODE == 'view':
        manager.view()
    elif MODE == 'make':
        manager.make()
    else:
        print("未知模式，请设置 MODE 为 'view' 或 'make'")