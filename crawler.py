"""
GitHub Actions 用的爬虫
- 抓 YTS、EZTV、Nyaa 等公开资源
- 更新 data.js
"""
import json
import re
import time
import requests
from pathlib import Path

# 兼容 GitHub Actions 路径
DATA_FILE = Path(__file__).parent / "data.js"

# 已有的种子数据
if DATA_FILE.exists():
    text = DATA_FILE.read_text(encoding="utf-8")
    m = re.search(r"window\.MAGNET_DATA\s*=\s*(\[.*\]);", text, re.DOTALL)
    POOL = json.loads(m.group(1)) if m else []
else:
    POOL = []

print(f"[start] existing pool: {len(POOL)}")

HASH_RE = re.compile(r'urn:btih:([a-fA-F0-9]{40})', re.I)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MagnetBot/1.0)",
    "Accept": "*/*",
}

def add_magnet(magnet, name="", source="", size=""):
    m = HASH_RE.search(magnet)
    if not m:
        return
    h = m.group(1).lower()
    if any(x["hash"] == h for x in POOL):
        return
    POOL.append({
        "hash": h,
        "name": (name or h)[:200],
        "size": size,
        "category": "",
        "source": source[:60],
        "magnet": magnet if magnet.startswith("magnet:") else f"magnet:?xt=urn:btih:{h}",
    })

def safe_get(url, timeout=15):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        return r.text if r.status_code == 200 else ""
    except Exception as e:
        print(f"[err] {url}: {e}")
        return ""

# 1. YTS 电影
def crawl_yts():
    print("[crawl] YTS...")
    url = "https://yts.mx/api/v2/list_movies.json?limit=100&sort_by=date_added"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        data = r.json()
        if data.get("status") != "ok":
            return
        for movie in (data.get("data") or {}).get("movies") or []:
            title = movie.get("title_english") or movie.get("title") or "Unknown"
            year = movie.get("year", "")
            for t in movie.get("torrents", []):
                name = f"{title} {year} [{t.get('quality','')} {t.get('size','')}]"
                add_magnet(
                    f"magnet:?xt=urn:btih:{t['hash']}&tr=udp://open.demonii.com:1337/announce",
                    name=name, source="YTS", size=t.get("size", ""),
                )
        print(f"[YTS] ok, pool now: {len(POOL)}")
    except Exception as e:
        print(f"[YTS err] {e}")

# 2. ETTV / EZGTV 剧集
def crawl_eztv():
    print("[crawl] EZTV...")
    try:
        r = requests.get("https://eztv.io/api/get-torrents?limit=200",
                         headers=HEADERS, timeout=20)
        for t in r.json().get("torrents", []):
            name = f"{t.get('show','')} S{t.get('season','')}E{t.get('episode','')} [{t.get('quality','')}]"
            h = t.get("hash", "")
            if h:
                add_magnet(
                    f"magnet:?xt=urn:btih:{h}&tr=udp://tracker.openbittorrent.com:80",
                    name=name, source="EZTV", size="",
                )
        print(f"[EZTV] ok, pool now: {len(POOL)}")
    except Exception as e:
        print(f"[EZTV err] {e}")

# 3. Nyaa 动漫
def crawl_nyaa():
    print("[crawl] Nyaa...")
    try:
        r = requests.get("https://nyaa.si/?page=rss&c=1_0&f=0", headers=HEADERS, timeout=20)
        for m in re.finditer(r'urn:btih:([a-fA-F0-9]{40})', r.text):
            # 从上下文找标题
            h = m.group(1)
            start = max(0, m.start() - 500)
            ctx = r.text[start:m.start()]
            title_m = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', ctx)
            if title_m:
                name = title_m.group(1)[:150]
            else:
                name = h
            add_magnet(
                f"magnet:?xt=urn:btih:{h}&tr=udp://open.demonii.com:1337/announce",
                name=name, source="Nyaa", size="",
            )
        print(f"[Nyaa] ok, pool now: {len(POOL)}")
    except Exception as e:
        print(f"[Nyaa err] {e}")

# 跑所有源
crawl_yts()
time.sleep(2)
crawl_eztv()
time.sleep(2)
crawl_nyaa()

# 去重 + 限制大小(避免 data.js 太大)
seen = set()
unique = []
for m in POOL:
    if m["hash"] not in seen:
        seen.add(m["hash"])
        unique.append(m)
POOL = unique[-3000:]  # 最多保留 3000 条

print(f"[final] {len(POOL)} magnets")

# 写回 data.js
DATA_FILE.write_text(
    "window.MAGNET_DATA = " + json.dumps(POOL, ensure_ascii=False) + ";",
    encoding="utf-8",
)
print(f"[write] {DATA_FILE}")
