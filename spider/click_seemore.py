from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
import time
from bs4 import BeautifulSoup
import json
import re

def scrape_cases(url, json_file):
    """
    爬取目标页面的所有病例 (点击 "查看更多" 直到末尾)
    并将 title 和 href 保存为 JSON 文件
    """

    service = Service("msedgedriver.exe") # 请下载与 edge 浏览器版本对应的 msedgedriver.exe, 放入此文件所在目录
    driver = webdriver.Edge(service=service)

    driver.get(url)
    time.sleep(2)

    prev_last_href = None  # 上一次最后一个病例的 href

    while True:
        # 当前病例数
        li_elements = driver.find_elements(By.CSS_SELECTOR, ".li")
        current_count = len(li_elements)

        if current_count == 0:
            print("页面没有病例, 停止")
            break

        # 获取最后一个病例的 href 作为标识
        last_li = li_elements[-1]
        last_a = last_li.find_element(By.CSS_SELECTOR, "a.name")
        last_href = last_a.get_attribute("href")

        if last_href == prev_last_href:
            print("最后一个病例未变化, 停止迭代")
            break

        prev_last_href = last_href

        try:
            btn = driver.find_element(By.LINK_TEXT, "查看更多")
            driver.execute_script("arguments[0].scrollIntoView();", btn)
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(1)  # 等待新内容加载
        except:
            print("没有更多按钮或发生异常, 停止")
            break

    html = driver.page_source
    driver.quit()

    # 解析 HTML
    soup = BeautifulSoup(html, "html.parser")
    cases = []

    for li in soup.select(".li"):
        a_tag = li.select_one("a.name")
        title_tag = li.select_one(".sp")

        if a_tag and title_tag:
            title = title_tag.get_text(strip=True)
            href = a_tag["href"]

            if not href.startswith("http"):
                href = "https://bingli.iiyi.com" + href

            # 提取病例 ID
            match = re.search(r'/show/(\d+)-', href)

            case_id = None
            alternate_url = None

            if match:
                case_id = match.group(1)
                alternate_url = f"https://m.iiyi.com/bl/d-{case_id}.html"

            cases.append({
                "title": title,
                "url": href,
                "alternate_url": alternate_url
            })

    # 保存 JSON
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)

    print(f"共提取 {len(cases)} 个病例, 保存到 {json_file}")
    return cases


# ========================
# 调用示例
# ========================
if __name__ == "__main__":
    # scrape_cases("https://bingli.iiyi.com/cull/", "selected_cases.json") # 精选病例
    scrape_cases("https://bingli.iiyi.com/news/", "new_cases.json") # 最新病例
    # scrape_cases("https://bingli.iiyi.com/", "recommended_cases.json") # 推荐病例