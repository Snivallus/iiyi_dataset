# iiyi Dataset

This repository contains scripts for constructing a medical case dataset from [iiyi.com](https://bingli.iiyi.com/).

---

## Folder Structure

```bash
iiyi_dataset/
├── README.md       # This file
├── .gitignore
├── requirements.txt
├── spider/         # Web crawling scripts
│   ├── README.md   # Spider documentation
│   └── ...
├── case_filter.py      # Filter raw cases using Baichuan2
├── case_statistics.py  # Analyze case field statistics
├── case_rewrite.py     # Rewrite cases using DeepSeek
├── case_final.py       # Final filtering of rewritten cases
├── results/            # Final results
│   ├── images/
│   │    ├── case_0000/
│   │    ├── case_0001/
│   │    └── ...
│   └── cases.json
├── quick_start_of_Baichuan2.py # Example script for running Baichuan2
└── utils.py                    # Helper functions
```

---

## Pipeline

### 0. Virtual Environment

Create and activate a Python virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 1. Data Crawling

Follow the instructions in [spider/README.md](https://github.com/Snivallus/iiyi_dataset/blob/main/spider/README.md) to crawl full case content, and associated images.

```bash
iiyi_dataset/
├── spider/
│   ├── succeeded_cases.json    # Cases that have been successfully crawled
│   ├── failed_cases.json       # Cases that failed to be crawled
│   ├── raw_images/             # Images downloaded from the website
│   │   ├── case_0000/
│   |   |   ├── img_00.jpg
│   |   |   ├── img_01.jpg
│   |   |   └── ...
│   │   ├── case_0001/
│   |   |   ├── img_00.jpg
│   |   |   ├── img_01.jpg
│   |   |   └── ...
│   │   └── ...
│   └── ...
└── ...
```

### 2. Data Filtering Using Baichuan2

Run `case_filter.py` to filter `spider/succeeded_cases.json` and `spider/raw_images/` to get:

```bash
iiyi_dataset/
├── spider/
│   ├── filtered_cases.json    # Filtered cases
│   ├── filtered_images/       # Filtered images
│   │   ├── case_0000/
│   |   |   ├── img_00.jpg
│   |   |   ├── img_01.jpg
│   |   |   └── ...
│   │   ├── case_0001/
│   |   |   ├── img_00.jpg
│   |   |   ├── img_01.jpg
│   |   |   └── ...
│   │   └── ...
│   └── ...
└── ...
```

This step removes invalid cases and their coresponding images using [Baichuan2-13B-Chat](https://huggingface.co/baichuan-inc/Baichuan2-13B-Chat),     
which takes about one hour to complete on two NVIDIA GeForce RTX 4090 GPUs, which is kinds of slow—but free.  
You can experiment with the model using `quick_start_of_Baichuan2.py`.

### 3. Analyze case statistics

Run `case_statistics.py` on `spider/filtered_cases.json` to get something like:

```bash
内容.病案介绍.个人史
  count: 793
  types: {'str': 793}
  examples:
    - 否认不良嗜好，无吸烟酗酒史，否认毒物接触史。
    - 患者平素无明显不良嗜好，否认长期吸烟饮酒史。
    - 饮白酒半斤/天×40余年，未戒；吸烟20支/天×40余年，未戒；

内容.病案介绍.主诉
  count: 3021
  types: {'str': 3021}
  examples:
    - 扭伤致右膝关节疼痛、肿胀伴活动受限16天
    - 孕17+2周，要求引产
    - 不慎摔伤腰背部一天余
```

Thus, it helps us to determine useful patterns for the case rewriting stage.

### 4. Rewrite Cases Using DeepSeek

This step uses DeepSeek to reorganize the raw case content into a structured format.  
Run `case_rewrite.py` to get `spider/rewritten_cases.json`.

```bash
iiyi_dataset/
├── spider/
│   ├── rewritten_cases.json    # Rewritten cases
│   └── ...
└── ...
```

This step takes about 24 hours to complete because DeepSeek is relatively slow.  
The total token usage is around 6 million, which costs approximately 12 RMB.

### 5. Final Filtering

This step filters those cases that diagnoses is absent.
Run `case_final.py` on `spider/rewritten_cases.json` to get `results/`.

```bash
iiyi_dataset/
├── results/
│   ├── cases.json    # Final cases
│   ├── images/       # Final images
│   │   ├── case_0000/
│   |   |   ├── img_00.jpg
│   |   |   ├── img_01.jpg
│   |   |   └── ...
│   │   ├── case_0001/
│   |   |   ├── img_00.jpg
│   |   |   ├── img_01.jpg
│   |   |   └── ...
│   │   └── ...
│   └── ...
└── ...
```