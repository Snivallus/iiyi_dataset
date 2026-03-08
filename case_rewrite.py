# Run `export DEEPSEEK_API_KEY=your_key` in shell before executing this script.
import os
import json
import re
from utils import Tee, dump_case_incrementally # help functions from utils.py
from openai import OpenAI
import time

# ======================
# Redirect stdout/stderr to log file
# ======================
import sys
from datetime import datetime

LOG_DIR = "./logs"
os.makedirs(LOG_DIR, exist_ok=True)

log_file = os.path.join(
    LOG_DIR,
    f"run_rewrite_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)

sys.stdout = Tee(log_file)
sys.stderr = sys.stdout

print(f"[LOG] Logging started: {log_file}")

# ======================
# DeepSeek client
# ======================
api_key = os.environ.get("DEEPSEEK_API_KEY")

if not api_key:
    raise ValueError("DEEPSEEK_API_KEY not set")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)

# ======================
# Case -> text
# ======================
def case_to_text(case):

    parts = []
    seen_values = set()  # 用于去重

    def stringify_dict(d):
        """将 dict 转为 - key: value 格式"""
        items = []

        for k, v in d.items():
            if isinstance(v, str):
                if v not in seen_values:
                    items.append(f"- {k}: {v}")
                    seen_values.add(v)
            elif isinstance(v, dict):
                sub = stringify_dict(v)
                if sub:
                    items.append(f"- {k}: {sub}")

        return "; ".join(items)

    for key, value in case.items():

        # 跳过非文本字段
        if key in ("case_idx", "url", "images"):
            continue

        if isinstance(value, str):
            if value not in seen_values:
                parts.append(f"【{key}】{value}")
                seen_values.add(value)

        elif isinstance(value, dict):
            text = stringify_dict(value)
            if text:
                parts.append(f"【{key}】{text}")

    case_text = "\n".join(parts)
    print(f"case text length: {len(case_text)}\n")
    print(f"{case_text}\n")

    return case_text

# ======================
# 提示词模板
# ======================
PROMPT_TEMPLATE = """
你是一名医学病例整理助手。你的任务是根据给定的原始病例数据，整理并生成结构化医学病例信息。

请严格遵循以下原则：

【总体原则】

1. 根据提供的原始病例数据进行整理，不可以编造任何信息。
2. 尽量保留原始文本中的医学术语和专业表达（如果术语书写正确）。
3. 可以对句子进行适度整理，使其更规范、语句更通畅，但不得改变医学含义。
4. 如果某个字段在原始数据中没有明确内容，请填写 ""（空字符串）。
5. 不要输出解释，不要输出额外文本，只输出最终结构化结果。

【字段整理要求】

标题：
- 根据原始标题进行专业化改写
- 使用医学陈述语气
- 尽量简洁
- 不使用口语表达
- 示例：
  原始标题：中年女教师反复脐血流异常，原来是胎盘植入
  改写后：胎盘植入致脐血流异常一例

关键词：
- 提取 3–6 个医学关键词
- 优先选择疾病、检查方法、治疗方式等
- 用中文分号 "；" 分隔

基本信息：
- 提取患者性别、年龄、职业等基本信息
- 尽量保持原始表达

主诉：
- 患者最主要症状 + 持续时间

现病史：
- 描述疾病发生和发展的过程

既往史：
- 既往疾病、手术史、慢性病史等

个人史：
- 吸烟史、饮酒史、职业暴露等

家族史：
- 家族遗传疾病或重要疾病史

查体：
- 体格检查结果
- 同时可以加入诊治过程中与查体相关的检查描述

辅助检查：
- 实验室检查、影像学检查、病理检查等
- 同时可以加入诊治过程中与辅助检查相关的检查描述

诊断依据：
- 根据症状、查体、辅助检查等总结诊断依据

诊断结果：
- 最终明确诊断
- 多个诊断用中文分号 "；" 分隔

治疗方案：
- 医生制定的治疗计划

治疗经过：
- 描述实施治疗方案的过程
- 包括手术、药物治疗以及最终治疗结果

【输出格式】

必须严格按照以下 JSON 格式输出：

{{
"标题": "",
"关键词": "",
"基本信息": "",
"主诉": "",
"现病史": "",
"既往史": "",
"个人史": "",
"家族史": "",
"查体": "",
"辅助检查": "",
"诊断依据": "",
"诊断结果": "",
"治疗方案": "",
"治疗经过": ""
}}

下面是原始病例数据：

{case_text}"""

# ======================
# 生成
# ======================
def generate_json(prompt, temperature=0.7, max_tokens=1024):

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": "你是一名医学病例结构化整理助手。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False
    )

    return response.choices[0].message.content


# ======================
# 提取 JSON
# ======================
def extract_json(text):

    text = text.replace("```json", "").replace("```", "")

    match = re.search(r"\{[\s\S]*\}", text)

    if match:
        return match.group(0)

    return None


def safe_load_json(text):

    try:
        return json.loads(text)
    except:

        text = re.sub(r",\s*}", "}", text)
        text = re.sub(r",\s*]", "]", text)

        try:
            return json.loads(text)
        except:
            return None


# ======================
# Main rewrite
# ======================
def rewrite(
    input_json,
    output_json,
    temperature,
    max_tokens,
    max_retries
):

    # -------------------
    # load dataset
    # -------------------
    with open(input_json, encoding="utf-8") as f:
        data = json.load(f)

    cases = data["cases"]

    new_cases = []
    failed_case_ids = []

    metadata = {
        "total_input_cases": len(cases),
        "processed_cases": 0,
        "failed_cases": 0,
        "failed_case_ids": failed_case_ids
    }

    # -------------------
    # loop
    # -------------------
    for case in cases:

        idx = case["case_idx"]

        print(f"\n===== case {idx} =====")

        case_text = case_to_text(case)

        prompt = PROMPT_TEMPLATE.format(case_text=case_text)

        success = False

        # -------------------
        # retry loop
        # -------------------
        for attempt in range(1, max_retries + 1):

            print(f"attempt {attempt}/{max_retries}")

            try:

                response = generate_json(prompt, temperature, max_tokens)

                print("model output:")
                print(response)

                json_str = extract_json(response)

                if not json_str:

                    print("JSON extraction failed")
                    raise ValueError("JSON extraction failed")

                parsed = safe_load_json(json_str)

                if not parsed:

                    print("JSON parse failed")
                    raise ValueError("JSON parse failed")

                # -------------------
                # build new case
                # -------------------
                new_case = {
                    "case_idx": case["case_idx"],
                    "url": case["url"],
                    "images": case.get("images", [])
                }

                new_case.update(parsed)

                new_cases.append(new_case)

                metadata["processed_cases"] += 1

                print(f"saved case {idx}")

                success = True
                break

            except Exception as e:

                print(f"error in case {idx}, attempt {attempt}")
                print(e)

                if attempt < max_retries:
                    sleep_time = 2 ** attempt
                    print(f"retrying in {sleep_time}s...")
                    time.sleep(sleep_time)

        # -------------------
        # all retries failed
        # -------------------
        if not success:

            print(f"case {idx} FAILED after {max_retries} retries")

            metadata["failed_cases"] += 1
            failed_case_ids.append(idx)

        # -------------------
        # incremental save
        # -------------------
        dump_case_incrementally(output_json, metadata, new_cases)

        time.sleep(1)

    print("\ndone")


if __name__ == "__main__":

    # rewrite(
    #     input_json="spider/test/test_filtered_cases.json",
    #     output_json="spider/test/test_rewritten_cases.json",
    #     temperature=0.7,
    #     max_tokens=8192,
    #     max_retries=5
    # )

    rewrite(
        input_json="spider/filtered_cases.json",
        output_json="spider/rewritten_cases.json",
        temperature=0.7,
        max_tokens=8192,
        max_retries=5
    )