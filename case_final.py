import os
import json
from pathlib import Path
from utils import dump_case_incrementally, copy_images


def filter_cases(
    input_json,
    case_with_images_json,
    case_without_images_json,
    discard_json,
    image_root,
    new_image_root
):

    with open(input_json, encoding="utf-8") as f:
        data = json.load(f)

    cases = data["cases"]

    cases_with_images = []
    cases_without_images = []
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

        imgs = case.get("images", [])

        # -------------------
        # case 有图片
        # -------------------
        if imgs:

            new_idx = len(cases_with_images)

            new_case = case.copy()
            new_case["case_idx"] = new_idx

            old_paths = [
                os.path.join(image_root, img)
                for img in imgs
            ]

            new_paths = copy_images(old_paths, new_idx, new_root)

            new_case["images"] = new_paths

            cases_with_images.append(new_case)

            print(f"Keep case {old_idx} → with_images {new_idx}")

        # -------------------
        # case 没有图片
        # -------------------
        else:

            new_idx = len(cases_without_images)

            new_case = case.copy()
            new_case["case_idx"] = new_idx

            # 删除 images 字段
            new_case.pop("images", None)

            cases_without_images.append(new_case)

            print(f"Keep case {old_idx} → without_images {new_idx}")

    # -------------------
    # 保存结果
    # -------------------
    dump_case_incrementally(
        case_with_images_json,
        {"total_cases": len(cases_with_images)},
        cases_with_images
    )

    dump_case_incrementally(
        case_without_images_json,
        {"total_cases": len(cases_without_images)},
        cases_without_images
    )

    dump_case_incrementally(
        discard_json,
        {"discarded_cases": len(discarded_cases)},
        discarded_cases
    )

    print("\nFinal filtering done.")
    print("Cases with images:", len(cases_with_images))
    print("Cases without images:", len(cases_without_images))
    print("Discarded cases:", len(discarded_cases))


if __name__ == "__main__":

    filter_cases(
        input_json="spider/rewritten_cases.json",
        case_with_images_json="results/case_with_images.json",
        case_without_images_json="results/case_without_images.json",
        discard_json="results/discarded_cases.json",
        image_root="spider/filtered_images",
        new_image_root="results/images"
    )