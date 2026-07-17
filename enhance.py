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
    name = re.sub(r'\b(2160p|UHD|BluRay|REMUX|HDR|HEVC|H265|x265|H\.?264|x264|10bit|WEB-?DL|DV|DoVi|Atmos|TrueHD|DTS|HD|MA|RERIP|PROPER|REPACK|IMAX|Hybrid|DV\b.*)\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s{2,}', ' ', name)
    return name.strip()

def search_tmdb(title: str, year: str = "") -> int | None:
    """搜索 TMDB 返回电影 ID"""
    url = f"https://www.themoviedb.org/search?query={title}&language=zh-CN"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
    except:
        return None

    # 找到 movie 区域的链接
    for a in soup.find_all("a", href=re.compile(r'/movie/\d+')):
        href = a["href"]
        m = re.match(r'/movie/(\d+)', href)
        if not m:
            continue
        mid = int(m.group(1))
        
        # 检查是否在正确区域（排除 TV/people 等）
        parent = a.find_parent()
        for _ in range(5):
            if parent is None:
                break
            # 如果是 card 容器，检查类型
            cls = parent.get("class", [])
            if "card" in str(cls).lower():
                # 确认是 movie 类型
                result_type = parent.get("data-media-type", "")
                if result_type == "movie" or not result_type:
                    return mid
                break
            parent = parent.find_parent()
        
        # 如果没有 card 容器，直接返回第一个 movie
        return mid

    return None

def get_movie_detail(movie_id: int) -> dict | None:
    """获取 TMDB 影片详情"""
    url = f"https://www.themoviedb.org/movie/{movie_id}?language=zh-CN"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
    except:
        return None

    info = {}

    # og:image (海报)
    og_img = soup.find("meta", property="og:image")
    if og_img and og_img.get("content"):
        poster = og_img["content"]
        # 升级到高质量
        poster = poster.replace("/w500/", "/w780/")
        info["poster"] = poster

    # 评分
    rating_el = soup.find("div", class_="user_score_chart")
    if rating_el:
        pct = rating_el.get("data-percent", "")
        if pct:
            info["rating"] = str(int(pct) / 10)  # 78% -> 7.8

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

    # 上映日期
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
        
        # 提取年份
        year_match = re.search(r'\.(\d{4})\.', name)
        year = year_match.group(1) if year_match else ""
        
        print(f"[{idx+1}/{len(waiting)}] {title[:45]} ... ", end="", flush=True)

        movie_id = search_tmdb(title, year)
        if not movie_id:
            print("❌ 未找到")
            time.sleep(1 + random.random())
            continue

        time.sleep(0.8 + random.random() * 0.5)
        detail = get_movie_detail(movie_id)

        if detail and detail.get("poster"):
            item["poster"] = detail.get("poster", "")
            item["rating"] = detail.get("rating", "")
            item["genres"] = detail.get("genres", [])
            item["overview"] = detail.get("overview", "")
            item["year"] = detail.get("year", year)
            enhanced += 1
            print(f"✅ {detail.get('rating','?')}")
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
