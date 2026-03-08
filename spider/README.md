# iiyi Case Spider

This folder contains the spider scripts used to crawl medical case data from [iiyi.com](https://bingli.iiyi.com/).

---

## Folder Structure

```bash
spider/
├── README.md           # This file
├── .gitignore
├── click_seemore.py    # Crawl case titles and URLs from the website
├── merge_cases.py      # Merge multiple case lists into one
├── crawl_cases.py      # Crawl full case content and download images
└── merged_cases.py     # The merged case list (contains only titles and URLs)
```

Most generated files are ignored by `.gitignore`, except for `merged_cases.json`,  
which records the merged case list used for crawling.

---

## Data Crawling Pipeline

The sub-workflow consists of three steps.

### 1. Crawl case lists

Run `click_seemore.py` to crawl case titles and URLs from the website.  
This script is executed three times to collect cases from different sections:
- [推荐案例](https://bingli.iiyi.com/)
- [精选案例](https://bingli.iiyi.com/cull/)
- [最新案例](https://bingli.iiyi.com/news/)

Generated files:
- `recommended_cases.json`
- `selected_cases.json`
- `newest_cases.json`

Each file contains only case titles and URLs.   

Note that `msedgedriver.exe` is required by `click_seemore.py` for browser automation.  
You can download it from [here](https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/).  
Make sure the version aligns with your Edge browser version.

### 2. Merge case lists

Run `merge_cases.py` to merges the three case lists into `merged_cases.json`.  
This file contains deduplicated case titles and URLs and serves as the input for the next step.

### 3. Crawl full case content

Run `crawl_cases.py` with `merged_cases.json` as input to crawl full case content and download images.

```bash
Spider/
├── succeeded_cases.json    # Cases that have been successfully crawled
├── failed_cases.json       # Cases that failed to be crawled
├── raw_images/             # Images downloaded from the website
│   ├── case_0000/
|   |   ├── img_00.jpg
|   |   ├── img_01.jpg
|   |   └── ...
│   ├── case_0001/
|   |   ├── img_00.jpg
|   |   ├── img_01.jpg
|   |   └── ...
│   └── ...
└── ...
```