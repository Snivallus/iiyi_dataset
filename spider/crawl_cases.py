import os
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import random
import shutil

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def download_image(url, save_path):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(r.content)
            return True
    except:
        pass
    return False


def parse_case(url, case_idx, image_root):

    r = requests.get(url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")

    case = {}
    case["case_idx"] = case_idx
    case["url"] = url

    # =====================
    # 1 标题
    # =====================
    title_tag = soup.select_one(".article-details h1")
    case["标题"] = title_tag.get_text(strip=True) if title_tag else ""

    # =====================
    # 2 keywords description
    # =====================
    kw = soup.find("meta", {"name": "keywords"})
    desc = soup.find("meta", {"name": "description"})

    case["关键词"] = kw["content"] if kw else ""
    case["简要描述"] = desc["content"] if desc else ""

    # =====================
    # 3 摘要
    # =====================
    abstract = {}

    for p in soup.select(".abstract p"):
        key_tag = p.find("span")
        val_tag = p.find("var")

        if key_tag and val_tag:
            key = key_tag.get_text(strip=True)
            key = re.sub(r"[【】]", "", key)

            val = val_tag.get_text(strip=True)

            abstract[key] = val

    case["摘要"] = abstract

    # =====================
    # 4 病例正文
    # =====================
    content = {}

    container = soup.select_one(".case-container")

    if container:

        sections = container.find_all("h3")

        for sec in sections:

            sec_name = sec.get_text(strip=True)
            sec_name = re.sub(r"[【】]", "", sec_name)

            sec_content = {}
            text_buffer = []

            for node in sec.find_next_siblings():

                # 到下一个 section 停止
                if node.name == "h3":
                    break

                # 遇到版权块直接终止
                if node.get("class") and "Copyright-notice" in node.get("class"):
                    break

                if node.name == "div":

                    h5s = node.find_all("h5")

                    # ---------- 结构化 section ----------
                    if h5s:

                        for h5 in h5s:

                            sub_name = h5.get_text(strip=True)

                            p = h5.find_next_sibling("p")

                            if p:
                                sec_content[sub_name] = p.get_text(strip=True)

                    # ---------- 纯文本 section ----------
                    else:

                        text = node.get_text(" ", strip=True)

                        if text:
                            text_buffer.append(text)

            # 如果存在 h5 子结构
            if sec_content:
                content[sec_name] = sec_content

            # 如果没有 h5 → 纯文本
            elif text_buffer:
                content[sec_name] = "\n".join(text_buffer)

    case["内容"] = content

    # =====================
    # 5 图片下载
    # =====================
    folder_name = f"case_{case_idx:04d}"
    case_img_dir = os.path.join(image_root, folder_name)
    os.makedirs(case_img_dir, exist_ok=True)

    imgs = []

    for img in soup.select(".case-container img"):

        src = img.get("src") or img.get("data-src")

        if not src:
            continue

        # 跳过 base64 图片
        if src.startswith("data:"):
            continue

        # 构造完整 URL
        img_url = urljoin(url, src)

        imgs.append(img_url)

    # 去重 (有些页面会重复 img)
    imgs = list(dict.fromkeys(imgs))
    if imgs:
        has_img = True
    else:
        has_img = False
        shutil.rmtree(case_img_dir)

    saved_imgs = []

    for i, img_url in enumerate(imgs):

        file_name = f"img_{i:02d}.jpg"
        img_path = os.path.join(case_img_dir, file_name)

        ok = download_image(img_url, img_path)

        if ok:

            # 过滤过小图片 (UI图标)
            if os.path.getsize(img_path) < 5 * 1024:
                os.remove(img_path)
                continue

            saved_imgs.append(os.path.join(folder_name, file_name).replace("\\", "/"))

    case["images"] = saved_imgs

    return case, has_img


def append_json(file_path, data):
    """
    向 json list 文件追加一条数据
    """
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = json.load(f)
    else:
        content = []

    content.append(data)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)


def scrape_cases(
    input_json,
    output_json,
    image_root,
    failed_json,
    temp_json
):

    with open(input_json, encoding="utf-8") as f:
        cases = json.load(f)

    total_cases = 0
    cases_with_images = 0

    for idx, case in enumerate(cases):

        url = case.get("alternate_url")

        if not url:
            continue

        print(f"\nprocessing case {idx}: {url}")

        success = False

        for attempt in range(3):

            try:

                data, has_img = parse_case(url, idx, image_root)

                # 立即写入 temp
                append_json(temp_json, data)

                total_cases += 1
                if has_img:
                    cases_with_images += 1

                success = True
                break

            except Exception as e:

                print(f"attempt {attempt+1} failed:", e)
                time.sleep(random.uniform(3, 5))

        if not success:
            append_json(failed_json, case)

        # 随机间隔
        sleep_time = random.uniform(1, 2)
        print(f"sleep {sleep_time:.2f}s")
        time.sleep(sleep_time)

        # 偶尔长休眠
        if random.random() < 0.1:
            long_sleep = random.uniform(5, 10)
            print(f"long sleep {long_sleep:.2f}s")
            time.sleep(long_sleep)

    # =====================
    # 最终生成成功 JSON
    # =====================
    with open(temp_json, encoding="utf-8") as f:
        results = json.load(f)
    os.remove(temp_json)

    metadata = {
        "total_cases": total_cases,
        "cases_with_images": cases_with_images,
        "cases_without_images": total_cases - cases_with_images,
        "failed_cases": len(cases) - total_cases
    }

    output_data = {
        "metadata": metadata,
        "cases": results
    }

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print("\nDone")
    print("success:", total_cases)
    print("failed:", len(cases) - total_cases)


if __name__ == "__main__":

    # scrape_cases(
    #     input_json="test/test_cases.json",
    #     output_json="test/test_succeeded_cases.json",
    #     image_root="test/test_raw_images",
    #     failed_json="test/test_failed_cases.json",
    #     temp_json="test/test_temp.json"
    # )

    scrape_cases(
        input_json="merged_cases.json",
        output_json="succeeded_cases.json",
        image_root="raw_images",
        failed_json="failed_cases.json",
        temp_json="temp.json"
    )