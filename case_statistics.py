import json
from collections import defaultdict, Counter

def analyze_case_schema(json_file, max_examples=3):
    """
    统计 case 数据的字段结构：
    - 字段路径
    - 出现次数
    - 数据类型
    - 示例值
    """
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

    cases = data["cases"]

    # 字段统计
    field_count = Counter()

    # 字段类型统计
    field_types = defaultdict(Counter)

    # 示例值
    field_examples = defaultdict(list)

    def traverse(obj, path=""):
        """递归遍历 JSON"""
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_path = f"{path}.{k}" if path else k
                field_count[new_path] += 1
                field_types[new_path][type(v).__name__] += 1

                if (
                    isinstance(v, (str, int, float))
                    and len(field_examples[new_path]) < max_examples
                ):
                    field_examples[new_path].append(v)

                traverse(v, new_path)

        elif isinstance(obj, list):
            field_types[path]["list"] += 1
            for item in obj:
                traverse(item, path)

    # 遍历所有 case
    for case in cases:
        traverse(case)

    # ---------------------
    # 输出统计结果
    # ---------------------
    print("\n===== Field Statistics =====\n")

    for field in sorted(field_count):

        print(f"{field}")
        print(f"  count: {field_count[field]}")
        print(f"  types: {dict(field_types[field])}")

        if field_examples[field]:
            print(f"  examples:")
            for e in field_examples[field]:
                print(f"    - {str(e)[:120]}")

        print()


if __name__ == "__main__":

    analyze_case_schema("spider/filtered_cases.json")