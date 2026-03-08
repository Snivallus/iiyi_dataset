import os
import json
from pathlib import Path
from utils import dump_case_incrementally, copy_images


def filter_cases(
    input_json,
    output_json,
    discard_json,
    image_root,
    new_image_root
):

    with open(input_json, encoding="utf-8") as f:
        data = json.load(f)

    cases = data["cases"]

    kept_cases = []
    discarded_cases = []

    new_root = Path(new_image_root)

    for case in cases:

        old_idx = case["case_idx"]
        diagnosis = case.get("诊断结果", "").strip()

        # -------------------
        # 丢弃没有诊断结果的 case
        # -------------------
        if diagnosis == "":
            discarded_cases.append(case)
            print(f"Discard case {old_idx}: empty diagnosis")
            continue

        # -------------------
        # 保留 case
        # -------------------
        new_idx = len(kept_cases)

        new_case = case.copy()
        new_case["case_idx"] = new_idx

        # 复制图片
        imgs = case.get("images", [])

        old_paths = [
            os.path.join(image_root, img)
            for img in imgs
        ]

        new_paths = copy_images(old_paths, new_idx, new_root)

        new_case["images"] = new_paths

        kept_cases.append(new_case)

        print(f"Keep case {old_idx} → new case {new_idx}")

    # -------------------
    # 保存结果
    # -------------------
    dump_case_incrementally(
        output_json,
        {"total_cases": len(kept_cases)},
        kept_cases
    )

    dump_case_incrementally(
        discard_json,
        {"discarded_cases": len(discarded_cases)},
        discarded_cases
    )

    print("\nFinal filtering done.")


if __name__ == "__main__":

    filter_cases(
        input_json="spider/rewritten_cases.json",
        output_json="results/cases.json",
        discard_json="results/discarded_cases.json",
        image_root="spider/filtered_images",
        new_image_root="results/images"
    )