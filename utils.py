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