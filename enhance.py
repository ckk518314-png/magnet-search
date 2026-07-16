#!/usr/bin/env python3
"""增强 data.js：从豆瓣爬取海报、简介、评分等信息。纯自动化，无需 API Key。"""

import json
import re
import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

CACHE = {}  # 豆瓣搜索结果缓存

def extract_title(filename):
    """从文件名提取电影/剧集名称"""
    name = filename
    # 移除常见后缀标签
    name = re.sub(r'\b\d{4}\b.*$', '', name)  # 从年份开始截断
    name = re.sub(r'\.S\d{2}.*$', '', name)    # 剧集季号
    name = re.sub(r'\.COMPLETE.*$', '', name)
    name = re.sub(r'\.(19|20)\d{2}\..*$', '', name)
    # 替换点号为空格
    name = name.replace('.', ' ').strip()
    # 移除常见标签
    name = re.sub(r'\b(1080p|2160p|4K|UHD|BluRay|REMUX|HEVC|HDR|HDR10\+|WEB-DL|NF|AMZN|HMAX|HBO|ATVP|DSNP|HULU|CR|DDP|Atmos|x264|x265|AAC|DTS-HD|TrueHD)\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+', ' ', name).strip()
    return name if name else filename

def extract_year(filename):
    """从文件名提取年份"""
    match = re.search(r'\b((?:19|20)\d{2})\b', filename)
    return match.group(1) if match else ""

def search_douban(title, year=""):
    """搜索豆瓣电影/剧集，返回(海报URL, 简介, 评分, 类型, 导演, 演员)"""
    cache_key = f"{title}|{year}"
    if cache_key in CACHE:
        return CACHE[cache_key]

    try:
        search_url = f"https://movie.douban.com/subject_search?search_text={quote(title)}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = requests.get(search_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            CACHE[cache_key] = None
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # 获取第一个搜索结果
        item = soup.find("div", class_="item-root")
        if not item:
            # 试试直接跳转（豆瓣有时会直接跳转到详情页）
            detail_url = resp.url if "subject" in resp.url else None
            if not detail_url:
                CACHE[cache_key] = None
                return None
            # 直接爬详情页
            detail_resp = requests.get(detail_url, headers=headers, timeout=15)
            if detail_resp.status_code != 200:
                CACHE[cache_key] = None
                return None
            soup = BeautifulSoup(detail_resp.text, "html.parser")
            return parse_detail_page(soup, cache_key)

        # 获取详情页链接
        detail_link = item.find("a", class_="cover-link")
        if not detail_link:
            detail_link = item.find("a", href=re.compile(r"/subject/"))
        if not detail_link:
            CACHE[cache_key] = None
            return None

        detail_url = detail_link["href"]
        if not detail_url.startswith("http"):
            detail_url = "https://movie.douban.com" + detail_url

        time.sleep(random.uniform(1.5, 3))
        detail_resp = requests.get(detail_url, headers=headers, timeout=15)
        if detail_resp.status_code != 200:
            CACHE[cache_key] = None
            return None

        soup = BeautifulSoup(detail_resp.text, "html.parser")
        result = parse_detail_page(soup, cache_key)
        return result

    except Exception as e:
        print(f"  ⚠ 搜索 '{title}' 失败: {e}")
        CACHE[cache_key] = None
        return None

def parse_detail_page(soup, cache_key):
    """解析豆瓣详情页"""
    try:
        # 海报
        poster = ""
        poster_tag = soup.find("img", rel="v:image")
        if not poster_tag:
            poster_tag = soup.find("a", class_="nbgnbg")
            if poster_tag:
                poster_img = poster_tag.find("img")
                poster = poster_img["src"] if poster_img else ""
        else:
            poster = poster_tag.get("src", "")
        if poster:
            poster = poster.replace("/view/photo/m/public/", "/view/photo/l/public/")

        # 简介
        overview = ""
        summary_tag = soup.find("span", property="v:summary")
        if not summary_tag:
            summary_tag = soup.find("div", class_="indent", id="link-report")
            if summary_tag:
                summary_text = summary_tag.find("span", class_="all hidden")
                if not summary_text:
                    summary_text = summary_tag.find("span")
                overview = summary_text.get_text(strip=True) if summary_text else ""
        else:
            overview = summary_tag.get_text(strip=True)
        if overview:
            overview = overview[:300]

        # 评分
        rating = ""
        rating_tag = soup.find("strong", property="v:average")
        if rating_tag:
            rating = rating_tag.get_text(strip=True)

        # 类型
        genres = []
        for g in soup.find_all("span", property="v:genre"):
            genres.append(g.get_text(strip=True))
        genre_str = ", ".join(genres[:4]) if genres else ""

        # 导演
        director = ""
        dir_tag = soup.find("a", rel="v:directedBy")
        if dir_tag:
            director = dir_tag.get_text(strip=True)

        # 演员
        actors = []
        for a in soup.find_all("a", rel="v:starring")[:3]:
            actors.append(a.get_text(strip=True))
        cast_str = ", ".join(actors) if actors else ""

        result = (poster, overview, rating, genre_str, director, cast_str)
        CACHE[cache_key] = result
        return result

    except Exception as e:
        print(f"  ⚠ 解析详情页失败: {e}")
        CACHE[cache_key] = None
        return None

def enhance():
    print("🔍 开始从豆瓣获取影片详情...")

    with open("data.js", "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(r'window\.MAGNET_DATA\s*=\s*([\s\S]*?);', content)
    if not match:
        print("❌ 未找到 data.js 中的数据")
        return

    data = json.loads(match.group(1))
    total = len(data)
    print(f"📦 共 {total} 条数据待增强\n")

    enhanced_count = 0
    for idx, item in enumerate(data):
        name = item.get("name", "")
        title = extract_title(name)
        year = extract_year(name)

        # 跳过已有海报的条目
        if item.get("poster"):
            continue

        print(f"[{idx+1}/{total}] {title} ...", end=" ", flush=True)
        result = search_douban(title, year)

        if result:
            poster, overview, rating, genres, director, cast_str = result
            if poster:
                item["poster"] = poster
                enhanced_count += 1
            if overview:
                item["overview"] = overview
            if rating:
                item["rating"] = rating
            if genres:
                item["genres"] = genres
            if director:
                item["director"] = director
            if cast_str:
                item["cast"] = cast_str

            print(f"✅ 评分 {rating}" if rating else "✅")
        else:
            print("❌ 未找到")

        if (idx + 1) % 10 == 0:
            print(f"\n⏳ 已处理 {idx+1}/{total}，休息 5 秒...\n")
            time.sleep(5)

    # 写回 data.js
    print(f"\n💾 写入 data.js（共增强 {enhanced_count} 条海报）...")
    with open("data.js", "w", encoding="utf-8") as f:
        f.write("window.MAGNET_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";")

    print("✅ 增强完成！")

if __name__ == "__main__":
    enhance()
