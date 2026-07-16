#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
超详细多源磁力爬虫
- 支持站点：BTDigg, 海盗湾, 1337x, YTS, EZTV, LimeTorrents, Torrent9, Nyaa, 动漫花园, SkrBT, 磁力猫(示例)
- 关键词：中英日韩 + 成人内容（>1000个）
- 字段：name, magnet, size, seed, leech, date, source
- 并发请求，自动重试，反爬跳过
- 智能去重：磁力链前40字符 + 名称相似度(>0.85)
- 输出 data.js (window.MAGNET_DATA)
"""

import json
import time
import re
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher

# ================== 全局配置 ==================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
]
DELAY_RANGE = (1, 3)          # 随机延迟秒
MAX_RETRIES = 2               # 请求重试次数
MAX_WORKERS = 5               # 并发线程数
SIMILARITY_THRESHOLD = 0.85   # 名称去重相似度阈值

def safe_request(url, max_retries=MAX_RETRIES):
    """带随机UA、超时、重试的请求，失败返回None"""
    for _ in range(max_retries):
        try:
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            resp = requests.get(url, headers=headers, timeout=25)
            if resp.status_code == 200:
                return resp
            else:
                time.sleep(random.uniform(0.5, 2))
        except Exception:
            time.sleep(random.uniform(1, 3))
    return None

def parse_size(text):
    """从文本中提取文件大小（支持GB/MB/TB/KB）"""
    pattern = r'([\d.]+)\s*(GB|MB|TB|KB)'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1) + " " + match.group(2)
    return ""

def parse_date(text):
    """尝试从文本中提取日期（YYYY-MM-DD或YYYY-MM-DD HH:MM:SS）"""
    pattern = r'(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}:\d{2})?)'
    match = re.search(pattern, text)
    return match.group(1) if match else ""

# ================== 各站点爬取函数（独立异常隔离） ==================

def scrape_btdigg(query):
    """BTDigg (https://btdig.com)"""
    results = []
    try:
        for page in range(1, 4):
            url = f"https://btdig.com/search?q={quote(query)}&p={page}"
            resp = safe_request(url)
            if not resp:
                break
            soup = BeautifulSoup(resp.text, "html.parser")
            # BTDigg 结果在 a[href^=magnet:]
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("magnet:"):
                    name = a.get_text(strip=True)
                    if not name:
                        continue
                    size = parse_size(name)
                    # 日期通常在父级文本中，简化
                    date = parse_date(a.parent.get_text(strip=True)) if a.parent else ""
                    results.append({
                        "name": name,
                        "magnet": href,
                        "size": size,
                        "seed": "",
                        "leech": "",
                        "date": date,
                        "source": "BTDigg"
                    })
            if not results:
                break
            time.sleep(random.uniform(*DELAY_RANGE))
    except Exception as e:
        print(f"  ❌ BTDigg 失败: {e}")
    return results

# ... 文件其余部分保持不变，省略以节省空间 ...

# ================== 主函数 ==================

def main():
    print("🔥 开始多源磁力爬取...")
    all_data = []
    total = len(KEYWORDS)
    for idx, kw in enumerate(KEYWORDS):
        print(f"\n--- 进度 {idx+1}/{total}: 关键词 '{kw}' ---")
        results = fetch_all(kw)
        all_data.extend(results)
        # 关键词间随机间隔
        time.sleep(random.uniform(1, 4))

    print("\n📦 正在去重...")
    unique_data = deduplicate(all_data)

    # 写入 data.js（改为单行 minify，兼容前端正则并减小体积）
    with open("data.js", "w", encoding="utf-8") as f:
        f.write("window.MAGNET_DATA = " + json.dumps(unique_data, ensure_ascii=False, separators=(',', ':')) + ";")

    print(f"\n✅ 全部完成！共 {len(unique_data)} 条磁力链接")

if __name__ == "__main__":
    main()
