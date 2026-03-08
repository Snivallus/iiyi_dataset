import json

def merge_json_files(file1, file2, output_file):

    def load_cases(file):
        with open(file, encoding='utf-8') as f:
            return json.load(f)

    cases1 = load_cases(file1)
    cases2 = load_cases(file2)

    unique = {}

    for case in cases1 + cases2:
        url = case["url"]
        unique[url] = case

    result = list(unique.values())

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"合并完成: {len(result)} cases")

if __name__ == "__main__":
    merge_json_files("selected_cases.json", "new_cases.json", "merged_cases.json")
    merge_json_files("merged_cases.json", "recommended_cases.json", "merged_cases.json")