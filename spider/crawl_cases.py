import os
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import random
import shutil

# HTTP 请求头, 模拟浏览器访问, 避免被网站拦截
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def download_image(url, save_path):
    """
    下载图片并保存到本地

    参数
    - url : str
        图片 URL
    - save_path : str
        图片保存路径

    返回
    - bool
        下载成功返回 True, 否则 False
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)

        # 请求成功
        if r.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(r.content)
            return True

    except:
        # 下载失败直接返回 False
        pass

    return False


def parse_case(url, case_idx, image_root):
    """
    解析单个病例页面

    参数
    - url : str
        病例页面 URL
    - case_idx : int
        病例编号
    - image_root : str
        图片保存根目录

    返回
    - case : dict
        解析得到的病例结构化数据
    - has_img : bool
        是否包含有效图片
    """
    # 请求网页
    r = requests.get(url, headers=HEADERS, timeout=10)

    # 使用 BeautifulSoup 解析 HTML
    soup = BeautifulSoup(r.text, "html.parser")

    # 存储病例数据
    case = {}
    case["case_idx"] = case_idx
    case["url"] = url

    # =====================
    # 1. 标题
    # =====================
    title_tag = soup.select_one(".article-details h1")
    case["标题"] = title_tag.get_text(strip=True) if title_tag else "" # 获取标题文本

    # =====================
    # 2. 关键词 & 简要描述
    # =====================
    kw = soup.find("meta", {"name": "keywords"}) # meta keywords
    desc = soup.find("meta", {"name": "description"}) # meta description

    case["关键词"] = kw["content"] if kw else ""
    case["简要描述"] = desc["content"] if desc else ""

    # =====================
    # 3. 摘要
    # =====================
    abstract = {}

    # 遍历摘要部分的所有段落
    for p in soup.select(".abstract p"):

        key_tag = p.find("span")
        val_tag = p.find("var")

        if key_tag and val_tag:

            # 摘要字段名称
            key = key_tag.get_text(strip=True)

            # 去掉中文括号
            key = re.sub(r"[【】]", "", key)

            # 摘要内容
            val = val_tag.get_text(strip=True)

            abstract[key] = val

    case["摘要"] = abstract

    # =====================
    # 4. 病例正文
    # =====================
    content = {}

    # 病例内容主容器
    container = soup.select_one(".case-container")

    if container:

        # 每个 section 通常由 h3 标题开始
        sections = container.find_all("h3")

        for sec in sections:

            # section 名称
            sec_name = sec.get_text(strip=True)

            # 去掉中文括号
            sec_name = re.sub(r"[【】]", "", sec_name)

            sec_content = {}
            text_buffer = []

            # 遍历该 section 后面的所有节点
            for node in sec.find_next_siblings():

                # 到下一个 section 停止
                if node.name == "h3":
                    break

                # 遇到版权信息停止
                if node.get("class") and "Copyright-notice" in node.get("class"):
                    break

                # 内容通常在 div 中
                if node.name == "div":
                    # 若存在 h5 子标题, 则解析成字典
                    h5s = node.find_all("h5")
                    
                    if h5s:
                        for h5 in h5s:
                            sub_name = h5.get_text(strip=True)

                            # 找到该小标题对应段落
                            p = h5.find_next_sibling("p")

                            if p:
                                sec_content[sub_name] = p.get_text(strip=True)

                    # 若没有 h5 子标题, 则解析成纯文本
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
    # 5. 图片下载
    # =====================
    folder_name = f"case_{case_idx:04d}" # 每个病例一个图片文件夹

    case_img_dir = os.path.join(image_root, folder_name)
    os.makedirs(case_img_dir, exist_ok=True)

    imgs = []

    # 查找正文中的所有图片
    for img in soup.select(".case-container img"):

        # 有些网站使用 data-src 懒加载
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

        # 如果没有图片, 则删除空目录
        shutil.rmtree(case_img_dir)

    saved_imgs = []

    # 下载图片
    for i, img_url in enumerate(imgs):
        file_name = f"img_{i:02d}.jpg"
        img_path = os.path.join(case_img_dir, file_name)
        ok = download_image(img_url, img_path)

        if ok:
            # 过滤过小图片 (通常是 UI 图标)
            if os.path.getsize(img_path) < 5 * 1024:
                os.remove(img_path)
                continue

            # 保存相对路径
            saved_imgs.append(
                os.path.join(folder_name, file_name).replace("\\", "/")
            )

    case["images"] = saved_imgs

    return case, has_img


def append_json(file_path, data):
    """
    向 JSON 文件追加一条数据 (JSON list)

    参数
    - file_path : str
        JSON 文件路径
    - data : dict
        需要追加的数据
    """

    # 如果文件已经存在, 则先读取原有 JSON 内容
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = json.load(f)

    # 如果文件不存在, 则创建一个新的 list
    else:
        content = []

    # 将新数据追加到 list
    content.append(data)

    # 将更新后的数据重新写入 JSON 文件
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)


def scrape_cases(
    input_json,
    output_json,
    image_root,
    failed_json,
    temp_json
):
    """
    抓取病例
    
    参数
    - input_json : str
        输入 JSON 文件路径 (包含待抓取病例的 URL 列表)
    - output_json : str
        输出 JSON 文件路径 (包含所有成功抓取的病例)
    - image_root : str
        图片保存根目录
    - failed_json : str
        失败 JSON 文件路径 (包含所有抓取失败的病例)
    - temp_json : str
        临时 JSON 文件路径 (包含所有成功抓取的病例)
    """
    # 读取输入 JSON（包含待抓取病例的 URL 列表）
    with open(input_json, encoding="utf-8") as f:
        cases = json.load(f)

    # 统计变量
    total_cases = 0          # 成功解析的病例数量
    cases_with_images = 0    # 包含图片的病例数量

    # 遍历所有病例
    for idx, case in enumerate(cases):

        # 从 JSON 中获取病例页面 URL
        url = case.get("alternate_url")

        # 如果没有 URL 则跳过
        if not url:
            continue

        print(f"\nprocessing case {idx}: {url}")

        # 标记当前病例是否成功抓取
        success = False

        # 最多尝试 3 次（防止网络问题或服务器偶发错误）
        for attempt in range(3):

            try:

                # 解析病例页面
                data, has_img = parse_case(url, idx, image_root)

                # 立即写入临时 JSON 文件
                # 这样即使程序中断, 也不会丢失已经抓取的数据
                append_json(temp_json, data)

                total_cases += 1

                # 如果该病例包含图片
                if has_img:
                    cases_with_images += 1

                success = True
                break

            except Exception as e:

                # 如果解析失败, 打印错误信息
                print(f"attempt {attempt+1} failed:", e)

                # 随机等待 3~5 秒后重试
                time.sleep(random.uniform(3, 5))

        # 如果 3 次都失败, 记录到 failed_json
        if not success:
            append_json(failed_json, case)

        # 每个请求之间随机等待 1~2 秒, 防止被反爬虫程序识别出来
        sleep_time = random.uniform(1, 2)
        print(f"sleep {sleep_time:.2f}s")
        time.sleep(sleep_time)

        # 小概率触发长时间休眠, 模拟真人浏览行为
        if random.random() < 0.1:
            long_sleep = random.uniform(5, 10)
            print(f"long sleep {long_sleep:.2f}s")
            time.sleep(long_sleep)

    # 读取临时文件中保存的所有成功案例
    with open(temp_json, encoding="utf-8") as f:
        results = json.load(f)

    # 删除临时文件
    os.remove(temp_json)

    # 构建统计信息
    metadata = {
        "total_cases": total_cases, # 成功抓取病例总数
        "cases_with_images": cases_with_images, # 含图片病例数
        "cases_without_images": total_cases - cases_with_images, # 无图片病例数
        "failed_cases": len(cases) - total_cases # 抓取失败病例数
    }

    # 构建最终输出结构
    output_data = {
        "metadata": metadata,
        "cases": results
    }

    # 写入最终 JSON 文件
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    # 输出统计信息
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