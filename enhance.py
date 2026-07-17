#!/usr/bin/env python3
"""增强 data.js — TMDB 数据源（海报名/评分/类型/简介）"""
import re, json, time, sys, random
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

def extract_title(name: str) -> str:
    """从文件名提取搜索关键词"""
    name = re.sub(r'\.\d{4}\..*$', '', name).strip('.')
    name = name.replace('.', ' ')
    name = re.sub(r'\s+\d{4}$', '', name)
    name = re.sub(r'\b(2160p|UHD|BluRay|REMUX|EXTENDED|HDR10\+?|HDR|HEVC|H\.?26[45]|10bit|WEB-?DL|DV|DoVi|Atmos|TrueHD|DTS[- ]?(HD|MA|X)?|RERIP|PROPER|REPACK|IMAX|Hybrid|COMPLETE|AMZN|NF|DSNP|MIXED|Criterion|DDP?\.?\d*\.?\d*)\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\.S\d{2}.*$', '', name)
    name = re.sub(r'\s{2,}', ' ', name)
    return name.strip()

def search_tmdb(title: str) -> tuple[str, int] | None:
    """搜索 TMDB，返回 (media_type, id) 或 None。media_type 为 'movie' 或 'tv'"""
    url = f"https://www.themoviedb.org/search?query={title}&language=zh-CN"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
    except:
        return None

    # 按 card 里的 data-media-type 区分，优先 movie
    for media_type in ["movie", "tv"]:
        for a in soup.find_all("a", href=re.compile(rf'/{media_type}/\d+')):
            href = a["href"]
            m = re.match(rf'/{media_type}/(\d+)', href)
            if not m:
                continue
            mid = int(m.group(1))
            parent = a.find_parent()
            for _ in range(5):
                if parent is None:
                    break
                cls = str(parent.get("class", ""))
                if "card" in cls.lower():
                    result_type = parent.get("data-media-type", "")
                    if result_type == media_type or not result_type:
                        return (media_type, mid)
                    break
                parent = parent.find_parent()
            # 无 card 容器，直接返回第一个匹配
            return (media_type, mid)

    return None

def get_detail(media_type: str, media_id: int) -> dict | None:
    """获取 TMDB 影片/剧集详情"""
    url = f"https://www.themoviedb.org/{media_type}/{media_id}?language=zh-CN"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
    except:
        return None

    info = {}

    # og:title (中文名)
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        cn = og_title["content"].strip()
        cn = re.sub(r'\s*\(\d{4}\)\s*$', '', cn)
        info["title_cn"] = cn

    # og:image (海报)
    og_img = soup.find("meta", property="og:image")
    if og_img and og_img.get("content"):
        poster = og_img["content"]
        poster = poster.replace("/w500/", "/w780/")
        info["poster"] = poster

    # 评分
    rating_el = soup.find("div", class_="user_score_chart")
    if rating_el:
        pct = rating_el.get("data-percent", "")
        if pct:
            info["rating"] = str(int(pct) / 10)

    # 类型
    genres = []
    for span in soup.find_all("span", class_="genres"):
        for a in span.find_all("a"):
            genres.append(a.get_text(strip=True))
    info["genres"] = genres

    # 简介
    overview_el = soup.find("div", class_="overview")
    if overview_el:
        p = overview_el.find("p")
        if p:
            info["overview"] = p.get_text(strip=True)

    # 日期
    date_el = soup.find("span", class_="release_date")
    if date_el:
        txt = date_el.get_text(strip=True)
        m = re.search(r'(\d{4})', txt)
        if m:
            info["year"] = m.group(1)

    return info if info else None

def main(data_file: str, output_file: str):
    with open(data_file, "r", encoding="utf-8") as f:
        content = f.read()

    m = re.search(r'window\.MAGNET_DATA\s*=\s*([\s\S]*?);', content)
    items = json.loads(m.group(1))

    waiting = [(i, item) for i, item in enumerate(items) if not item.get("poster")]
    print(f"📦 共 {len(items)} 条，其中 {len(waiting)} 条待增强\n")

    enhanced = 0
    for idx, (i, item) in enumerate(waiting):
        name = item.get("name", "")
        title = extract_title(name)
        
        print(f"[{idx+1}/{len(waiting)}] {title[:45]} ... ", end="", flush=True)

        result = search_tmdb(title)
        if not result:
            print("❌ 未找到")
            time.sleep(1 + random.random())
            continue

        media_type, media_id = result
        time.sleep(0.8 + random.random() * 0.5)
        detail = get_detail(media_type, media_id)

        if detail:
            if detail.get("poster"):
                item["poster"] = detail["poster"]
                enhanced += 1
            if detail.get("title_cn"):
                item["title_cn"] = detail["title_cn"]
            if detail.get("rating"):
                item["rating"] = detail["rating"]
            if detail.get("genres"):
                item["genres"] = detail["genres"]
            if detail.get("overview"):
                item["overview"] = detail["overview"]
            if detail.get("year"):
                item["year"] = detail["year"]
            print(f"✅ {detail.get('rating','?')} [{media_type}]")
        else:
            print("❌ 无详情")

        time.sleep(1.5 + random.random() * 1)

    new_data = json.dumps(items, ensure_ascii=False, indent=2)
    header = content[:m.start()]
    footer = content[m.end():]
    new_content = header + "window.MAGNET_DATA = " + new_data + ";" + footer

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"\n💾 {output_file}")
    print(f"✅ 增强完成！{enhanced}/{len(waiting)}")

if __name__ == "__main__":
    data_file = sys.argv[1] if len(sys.argv) > 1 else "data.js"
    output_file = sys.argv[2] if len(sys.argv) > 2 else data_file
    main(data_file, output_file)
