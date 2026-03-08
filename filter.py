# Run `export HF_ENDPOINT=https://hf-mirror.com` in shell before executing this script 
# to use the mirror endpoint for faster downloads in China mainland.
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "3,4" # Environment settings

import json
import shutil
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM
from transformers.generation.utils import GenerationConfig
import re
from quick_start import load_model, load_tokenizer # help functions from quick_start.py

# ======================
# Model config
# ======================
MODEL_NAME = "baichuan-inc/Baichuan2-13B-Chat"
MODEL_REVISION = "v2.0"
CACHE_DIR = Path("./cache")

DTYPE = torch.bfloat16

MAX_CASE_TEXT_LENGTH = 3000 # 限制输入文本长度，避免显存爆炸
DUPLICATE_STRING_MIN_LEN = 10 # 判断不同 case 字符串完全重复的最小长度阈值

# ======================
# Redirect stdout/stderr to log file
# ======================
import sys
from datetime import datetime

LOG_DIR = "./logs"
os.makedirs(LOG_DIR, exist_ok=True)

log_file = os.path.join(
    LOG_DIR,
    f"run_filter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)

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

sys.stdout = Tee(log_file)
sys.stderr = sys.stdout

print(f"[LOG] Logging started: {log_file}")

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
    print(f"case text length: {len(case_text)}")
    if len(case_text) > MAX_CASE_TEXT_LENGTH:
        print(f"case text too long, truncated to {MAX_CASE_TEXT_LENGTH} chars")
        case_text = case_text[:MAX_CASE_TEXT_LENGTH]

    return case_text

# ======================
# Parse yes/no from model response
# ======================
def parse_yes_no(text):
    """
    从模型回答中提取 是/否
    """

    text = text.strip()
    m = re.search(r"^(是|否)", text.strip())

    if not m:
        return None

    return m.group()

# ======================
# Chat once and get yes/no
# ======================
def chat_once(model, tokenizer, prompt):

    messages = [{"role": "user", "content": prompt}]
    with torch.inference_mode():
        response = model.chat(tokenizer, messages)

    return response

# ======================
# Judge case with multiple votes
# ======================
def judge_case(model, tokenizer, prompt, vote_rounds):

    yes_count = 0
    no_count = 0

    for i in range(vote_rounds):
        resp = chat_once(model, tokenizer, prompt)

        decision = parse_yes_no(resp)

        if decision == "是":
            yes_count += 1
        elif decision == "否":
            no_count += 1

        print(f"vote {i+1}: {resp}")

        # 提前结束 (投票稳定化)
        if yes_count >= vote_rounds // 2 + 1:
            # 清理显存
            del resp
            torch.cuda.empty_cache()
            return True

        if no_count >= vote_rounds // 2 + 1:
            del resp
            torch.cuda.empty_cache()
            return False

        # 每轮都释放临时显存
        del resp
        torch.cuda.empty_cache()

    return yes_count > no_count


# ======================
# Copy images
# ======================
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

# ======================
# Dump cases incrementally (for debugging)
# ======================
def dump_case_incrementally(output_json, metadata, cases):
    output = {
        "metadata": metadata,
        "cases": cases
    }
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

# ======================
# 检查对象或其嵌套字典中是否有键名包含“诊断”
# ======================
def has_diagnosis_key(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if "诊断" in k:
                return True
            if isinstance(v, dict):
                if has_diagnosis_key(v):
                    return True
    return False

# ======================
# 收集所有诊断相关字段文本
# ======================
def collect_diagnosis_text(d):
    texts = []
    for k, v in d.items():
        if "诊断" in k and isinstance(v, str):
            texts.append(v)
        elif isinstance(v, dict):
            texts.extend(collect_diagnosis_text(v))
    return texts

# ======================
# Prompt
# ======================
PROMPT_TEMPLATE_1 = """
你是医学病例数据筛选助手。

任务：
判断病例中的诊断结果是否与标题所描述的内容相关联。

标题：{title}
诊断内容：{diagnosis_combined}

如果诊断与标题内容相关，回答：是
如果不相关，回答：否

不要输出解释，只输出“是”或“否”。
"""

PROMPT_TEMPLATE_2 = """
你是医学病例数据筛选助手。

任务：
判断下面的病例是否包含【明确诊断结果】。

“明确诊断结果”的定义：
1. 有清晰的疾病名称或临床诊断结论，无需猜测。
2. 排除“可能”、“疑似”、“待排查”等不确定表述。
3. 可以来自病例的任何部分，包括：
   - 标题
   - 简要描述
   - 摘要
   - 病案介绍
   - 诊治过程
   - 其他临床信息段落

注意：
- 只要病例文本中暗示了最终诊断结果，即使没有专门的“诊断”字段，也应判断为“是”。
- 如果病例没有任何明确或可推断的诊断信息，判断为“否”。
- 不要输出任何解释、理由或额外文本，只回答“是”或“否”。

病例：
{case_text}
"""

# ======================
# Main filtering
# ======================
def filter_cases(
    input_json,
    output_json,
    discard_json,
    image_root,
    new_image_root,
    vote_rounds,
    temperature=0.3,
    top_p=0.9,
    max_new_tokens=1
):
    tokenizer = load_tokenizer()

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        revision=MODEL_REVISION,
        device_map="auto",
        max_memory={0: "15GiB", 1: "15GiB"},
        torch_dtype=DTYPE,
        trust_remote_code=True,
        cache_dir=CACHE_DIR,
    )

    model.generation_config = GenerationConfig.from_pretrained(
        MODEL_NAME,
        revision=MODEL_REVISION,
        cache_dir=CACHE_DIR,
    )

    model.generation_config.temperature = temperature
    model.generation_config.top_p = top_p
    model.generation_config.max_new_tokens = max_new_tokens

    with open(input_json, encoding="utf-8") as f:
        data = json.load(f)

    cases = data["cases"]

    # -------------------
    # 去重（跨 case + 内部重复）
    # -------------------

    string_to_case_idx = {}
    case_idx_to_strings = {}
    case_string_count = {}

    for case in cases:

        case_idx = case["case_idx"]

        collected = []

        def collect_strings(obj, path=""):

            if isinstance(obj, str):

                collected.append((obj, path))

            elif isinstance(obj, dict):

                for k, v in obj.items():

                    new_path = f"{path}.{k}" if path else k

                    collect_strings(v, new_path)

            elif isinstance(obj, list):

                for i, v in enumerate(obj):

                    new_path = f"{path}[{i}]"

                    collect_strings(v, new_path)

        collect_strings(case)

        case_idx_to_strings[case_idx] = collected

        string_count = {}

        for s, path in collected:

            if len(s) < DUPLICATE_STRING_MIN_LEN:
                continue

            string_count[s] = string_count.get(s, 0) + 1

            if s not in string_to_case_idx:
                string_to_case_idx[s] = set()

            string_to_case_idx[s].add(case_idx)

        case_string_count[case_idx] = string_count

    # -------------------
    # 只删除：
    # 既跨 case 重复 AND 在本 case 内重复
    # -------------------

    duplicate_case_idx = {}

    for case_idx, string_count in case_string_count.items():

        for s, count in string_count.items():

            if count < 2:
                continue

            if len(string_to_case_idx.get(s, set())) <= 1:
                continue

            duplicate_case_idx.setdefault(case_idx, set()).add(s)

    kept_cases = []
    discarded_cases = []

    for case in cases:

        idx = case["case_idx"]

        if idx in duplicate_case_idx:

            discarded_cases.append(case)

            print(
                f"Duplicate (internal + cross-case), discard case {idx}, strings:\n"
                f"{duplicate_case_idx[idx]}\n"
            )

            continue

        # -------------------
        # 同一 case 内部重复
        # -------------------

        pairs = case_idx_to_strings[idx]

        string_paths = {}

        for s, path in pairs:

            if len(s) < DUPLICATE_STRING_MIN_LEN:
                continue

            string_paths.setdefault(s, []).append(path)

        repeated_strings = []

        for s, paths in string_paths.items():

            if len(paths) <= 1:
                continue

            non_title_paths = [p for p in paths if not p.startswith("标题")]

            if len(non_title_paths) <= 1:
                continue

            repeated_strings.append(s)

        if repeated_strings:

            def remove_repeated(obj, path=""):

                if isinstance(obj, dict):

                    keys_to_delete = []

                    for k, v in obj.items():

                        new_path = f"{path}.{k}" if path else k

                        if new_path == "标题":
                            continue

                        if isinstance(v, str) and v in repeated_strings:
                            keys_to_delete.append(k)

                        else:
                            remove_repeated(v, new_path)

                    for k in keys_to_delete:
                        del obj[k]

                elif isinstance(obj, list):

                    for i in range(len(obj) - 1, -1, -1):

                        v = obj[i]

                        if isinstance(v, str) and v in repeated_strings:
                            obj.pop(i)

                        else:
                            remove_repeated(v, f"{path}[{i}]")

            remove_repeated(case)

            case["重复描述"] = "；".join(repeated_strings)

            print(
                f"Internal repeated strings removed for case {idx}:\n"
                f"{repeated_strings}\n"
            )

        kept_cases.append(case)

    print(
        f"De-duplication done, kept {len(kept_cases)} cases, "
        f"discarded {len(discarded_cases)} cases\n"
    )

    # -------------------
    # 模型筛选（过滤明确诊断）
    # -------------------
    new_root = Path(new_image_root)

    final_kept_cases = []
    final_discarded_cases = discarded_cases.copy()

    for case in kept_cases:

        old_idx = case["case_idx"]

        if has_diagnosis_key(case):

            title = case.get("标题", "")

            diagnosis_texts = collect_diagnosis_text(case)

            diagnosis_combined = "；".join(diagnosis_texts)

            prompt = PROMPT_TEMPLATE_1.format(
                title=title,
                diagnosis_combined=diagnosis_combined
            )

            keep = judge_case(model, tokenizer, prompt, vote_rounds)

        else:

            case_text = case_to_text(case)

            prompt = PROMPT_TEMPLATE_2.format(case_text=case_text)

            keep = judge_case(model, tokenizer, prompt, vote_rounds)

        if keep:

            new_idx = len(final_kept_cases)

            new_case = case.copy()

            new_case["case_idx"] = new_idx

            imgs = case.get("images", [])

            old_paths = [os.path.join(image_root, img) for img in imgs]

            new_paths = copy_images(old_paths, new_idx, new_root)

            new_case["images"] = new_paths

            final_kept_cases.append(new_case)

            print(f"Kept case {old_idx} as new case {new_idx}\n")

        else:

            final_discarded_cases.append(case)

            print(f"Discarded by model case {old_idx}\n")

    # -------------------
    # 输出 JSON
    # -------------------

    dump_case_incrementally(
        output_json,
        {"total_cases": len(final_kept_cases)},
        final_kept_cases
    )

    dump_case_incrementally(
        discard_json,
        {"discarded_cases": len(final_discarded_cases)},
        final_discarded_cases
    )

    print("Filtering done.\n")


if __name__ == "__main__":

    # filter_cases(
    #     input_json="spider/test/test_succeeded_cases.json",
    #     output_json="spider/test/test_filtered_cases.json",
    #     discard_json="spider/test/test_discarded_cases.json",
    #     image_root="spider/test/test_raw_images",
    #     new_image_root="spider/test/test_filtered_images",
    #     vote_rounds=5
    # )

    filter_cases(
        input_json="spider/succeeded_cases.json",
        output_json="spider/filtered_cases.json",
        discard_json="spider/discarded_cases.json",
        image_root="spider/raw_images",
        new_image_root="spider/filtered_images",
        vote_rounds=5
    )