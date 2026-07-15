import json, requests, time
from bs4 import BeautifulSoup

results = []
keywords = ["4K", "1080p", "BluRay", "阿凡达", "复仇者"]
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

for keyword in keywords:
    url = f"https://thepiratebay.org/search/{keyword}/0/99/0"
    try:
        print(f"抓取: {keyword}")
        r = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            if a["href"].startswith("magnet:"):
                name = a.get_text(strip=True)
                if name and len(name) > 3:
                    results.append({"name": name[:80], "magnet": a["href"]})
        time.sleep(3)
    except Exception as e:
        print(f"失败: {e}")

seen = set()
unique = []
for item in results:
    key = item["magnet"][:40]
    if key not in seen:
        seen.add(key)
        unique.append(item)

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(unique, f, ensure_ascii=False, indent=2)

print(f"✅ 完成，共 {len(unique)} 条")
