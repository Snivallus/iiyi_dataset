# ======================
# Redirect stdout to file
# ======================
import sys
class Tee:
    def __init__(self, filename):
        self.file = open(filename, "a", encoding="utf-8")
        self.stdout = sys.stdout

    def write(self, message):
        self.stdout.write(message)
        self.file.write(message)

    def flush(self):
        self.stdout.flush()
        self.file.flush()


# ======================
# Dump cases incrementally (for debugging)
# ======================
import json
def dump_case_incrementally(output_json, metadata, cases):
    output = {
        "metadata": metadata,
        "cases": cases
    }
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


# ======================
# Copy images
# ======================
import os
import shutil
from pathlib import Path
def copy_images(old_paths, new_case_idx, new_root):

    new_paths = []
    new_root = Path(new_root)

    case_dir_name = f"case_{new_case_idx:04d}"
    case_img_dir = new_root / case_dir_name

    if not old_paths:
        return new_paths
    
    case_img_dir.mkdir(parents=True, exist_ok=True)
    
    for i, p in enumerate(old_paths):

        # 统一路径分隔符
        p = os.path.normpath(p)
        src = Path(p)

        if not src.exists():
            print("missing image:", src)
            continue

        filename = f"img_{i:02d}{src.suffix}"
        dst = case_img_dir / filename
        shutil.copy(src, dst)

        # 统一使用 POSIX 相对路径
        rel_path = f"{case_dir_name}/{filename}"
        new_paths.append(rel_path)

    return new_paths