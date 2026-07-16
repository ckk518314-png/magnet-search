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

def scrape_piratebay(query):
    """海盗湾 (https://thepiratebay.org)"""
    results = []
    try:
        url = f"https://thepiratebay.org/search/{quote(query)}/0/99/0"
        resp = safe_request(url)
        if not resp:
            return results
        soup = BeautifulSoup(resp.text, "html.parser")
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            # 名称
            name_tag = cells[1].find("a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            # 磁力链接
            magnet_tag = cells[1].find("a", href=True, string="[magnet]")
            if not magnet_tag:
                continue
            magnet = magnet_tag["href"]
            # 种子/做种 (cells[2] 为 seed, cells[3] 为 leech)
            seed = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            leech = cells[3].get_text(strip=True) if len(cells) > 3 else ""
            # 日期（可能在描述中，暂不提取）
            results.append({
                "name": name,
                "magnet": magnet,
                "size": "",
                "seed": seed,
                "leech": leech,
                "date": "",
                "source": "PirateBay"
            })
        time.sleep(random.uniform(*DELAY_RANGE))
    except Exception as e:
        print(f"  ❌ PirateBay 失败: {e}")
    return results

def scrape_1337x(query):
    """1337x (https://1337x.to) - 需二次请求获取磁力，此处仅示例"""
    results = []
    try:
        url = f"https://1337x.to/search/{quote(query)}/1/"
        resp = safe_request(url)
        if not resp:
            return results
        soup = BeautifulSoup(resp.text, "html.parser")
        # 结果在表格中，磁力链接需要通过详情页获取，此处只取名称
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "/torrent/" in href and not href.startswith("http"):
                name = link.get_text(strip=True)
                if name:
                    # 大小通常在附近，暂不提取
                    results.append({
                        "name": name,
                        "magnet": "",  # 需二次请求
                        "size": "",
                        "seed": "",
                        "leech": "",
                        "date": "",
                        "source": "1337x"
                    })
        time.sleep(random.uniform(*DELAY_RANGE))
    except Exception as e:
        print(f"  ❌ 1337x 失败: {e}")
    return results

def scrape_yts(query):
    """YTS (https://yts.mx) API 直接返回磁力"""
    results = []
    try:
        url = f"https://yts.mx/api/v2/list_movies.json?query_term={quote(query)}&limit=50"
        resp = safe_request(url)
        if resp:
            data = resp.json()
            for movie in data.get("data", {}).get("movies", []):
                title = movie.get("title_long", movie.get("title", ""))
                for torr in movie.get("torrents", []):
                    magnet = torr.get("url", "")
                    if magnet:
                        results.append({
                            "name": f"{title} ({torr.get('quality', '')})",
                            "magnet": magnet,
                            "size": torr.get("size", ""),
                            "seed": torr.get("seeds", ""),
                            "leech": torr.get("peers", ""),
                            "date": movie.get("date_uploaded", ""),
                            "source": "YTS"
                        })
        time.sleep(random.uniform(*DELAY_RANGE))
    except Exception as e:
        print(f"  ❌ YTS 失败: {e}")
    return results

def scrape_eztv(query):
    """EZTV (https://eztv.re)"""
    results = []
    try:
        url = f"https://eztv.re/search/{quote(query)}"
        resp = safe_request(url)
        if not resp:
            return results
        soup = BeautifulSoup(resp.text, "html.parser")
        for row in soup.find_all("tr", class_="forum_line"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            name_tag = cells[1].find("a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            magnet_tag = cells[2].find("a", href=True)
            if magnet_tag and magnet_tag["href"].startswith("magnet:"):
                results.append({
                    "name": name,
                    "magnet": magnet_tag["href"],
                    "size": "",
                    "seed": "",
                    "leech": "",
                    "date": "",
                    "source": "EZTV"
                })
        time.sleep(random.uniform(*DELAY_RANGE))
    except Exception as e:
        print(f"  ❌ EZTV 失败: {e}")
    return results

def scrape_limetorrents(query):
    """LimeTorrents (https://limetorrents.lol)"""
    results = []
    try:
        url = f"https://limetorrents.lol/search/{quote(query)}/"
        resp = safe_request(url)
        if not resp:
            return results
        soup = BeautifulSoup(resp.text, "html.parser")
        for row in soup.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) < 3:
                continue
            name_tag = cols[1].find("a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            # 磁力链接可能在多个a中
            magnet_links = row.find_all("a", href=True)
            magnet = ""
            for a in magnet_links:
                if a["href"].startswith("magnet:"):
                    magnet = a["href"]
                    break
            results.append({
                "name": name,
                "magnet": magnet,
                "size": "",
                "seed": "",
                "leech": "",
                "date": "",
                "source": "LimeTorrents"
            })
        time.sleep(random.uniform(*DELAY_RANGE))
    except Exception as e:
        print(f"  ❌ LimeTorrents 失败: {e}")
    return results

def scrape_torrent9(query):
    """Torrent9 (https://torrent9.pe)"""
    results = []
    try:
        url = f"https://torrent9.pe/search/{quote(query)}/"
        resp = safe_request(url)
        if not resp:
            return results
        soup = BeautifulSoup(resp.text, "html.parser")
        for item in soup.find_all("div", class_="torrent"):
            name_tag = item.find("a", class_="torrent-title")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            magnet_tag = item.find("a", href=True, string="Magnet")
            magnet = magnet_tag["href"] if magnet_tag else ""
            results.append({
                "name": name,
                "magnet": magnet,
                "size": "",
                "seed": "",
                "leech": "",
                "date": "",
                "source": "Torrent9"
            })
        time.sleep(random.uniform(*DELAY_RANGE))
    except Exception as e:
        print(f"  ❌ Torrent9 失败: {e}")
    return results

def scrape_nyaa(query):
    """Nyaa (https://nyaa.si) 动漫"""
    results = []
    try:
        url = f"https://nyaa.si/search?q={quote(query)}"
        resp = safe_request(url)
        if not resp:
            return results
        soup = BeautifulSoup(resp.text, "html.parser")
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            name_tag = cells[1].find("a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            magnet_tag = cells[2].find("a", href=True)
            magnet = magnet_tag["href"] if magnet_tag and magnet_tag["href"].startswith("magnet:") else ""
            seed = cells[3].get_text(strip=True) if len(cells) > 3 else ""
            leech = cells[4].get_text(strip=True) if len(cells) > 4 else ""
            results.append({
                "name": name,
                "magnet": magnet,
                "size": "",
                "seed": seed,
                "leech": leech,
                "date": "",
                "source": "Nyaa"
            })
        time.sleep(random.uniform(*DELAY_RANGE))
    except Exception as e:
        print(f"  ❌ Nyaa 失败: {e}")
    return results

def scrape_dmhy(query):
    """动漫花园 (https://share.dmhy.org)"""
    results = []
    try:
        url = f"https://share.dmhy.org/topics/list?keyword={quote(query)}"
        resp = safe_request(url)
        if not resp:
            return results
        soup = BeautifulSoup(resp.text, "html.parser")
        for row in soup.find_all("tr", class_="topic"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            name_tag = cells[1].find("a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            magnet_tag = row.find("a", href=True, string="磁力链接")
            magnet = magnet_tag["href"] if magnet_tag else ""
            results.append({
                "name": name,
                "magnet": magnet,
                "size": "",
                "seed": "",
                "leech": "",
                "date": "",
                "source": "DMHY"
            })
        time.sleep(random.uniform(*DELAY_RANGE))
    except Exception as e:
        print(f"  ❌ DMHY 失败: {e}")
    return results

def scrape_skrbt(query):
    """SkrBT (https://skrbt.com) 中文站"""
    results = []
    try:
        url = f"https://skrbt.com/search?q={quote(query)}"
        resp = safe_request(url)
        if not resp:
            return results
        soup = BeautifulSoup(resp.text, "html.parser")
        for item in soup.find_all("div", class_="result-item"):
            name_tag = item.find("a", class_="title")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            magnet_tag = item.find("a", href=True, string="磁力链接")
            magnet = magnet_tag["href"] if magnet_tag else ""
            results.append({
                "name": name,
                "magnet": magnet,
                "size": "",
                "seed": "",
                "leech": "",
                "date": "",
                "source": "SkrBT"
            })
        time.sleep(random.uniform(*DELAY_RANGE))
    except Exception as e:
        print(f"  ❌ SkrBT 失败: {e}")
    return results

def scrape_torrentgalaxy(query):
    """TorrentGalaxy (https://torrentgalaxy.to)"""
    results = []
    try:
        url = f"https://torrentgalaxy.to/torrents.php?search={quote(query)}&sort=id&order=desc"
        resp = safe_request(url)
        if not resp:
            return results
        soup = BeautifulSoup(resp.text, "html.parser")
        for row in soup.find_all("div", class_="tgxtablerow"):
            name_tag = row.find("a", title=True)
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            magnet_tag = row.find("a", href=True)
            magnet = ""
            for a in row.find_all("a", href=True):
                href = a.get("href", "")
                if href.startswith("magnet:"):
                    magnet = href
                    break
            size_cell = row.find("span", class_="badge-secondary")
            size = size_cell.get_text(strip=True) if size_cell else ""
            results.append({
                "name": name,
                "magnet": magnet,
                "size": size,
                "seed": "",
                "leech": "",
                "date": "",
                "source": "TorrentGalaxy"
            })
        time.sleep(random.uniform(*DELAY_RANGE))
    except Exception as e:
        print(f"  ❌ TorrentGalaxy 失败: {e}")
    return results

def scrape_torlock(query):
    """TorLock (https://torlock.com)"""
    results = []
    try:
        url = f"https://torlock.com/all/torrents/{quote(query)}.html"
        resp = safe_request(url)
        if not resp:
            return results
        soup = BeautifulSoup(resp.text, "html.parser")
        for article in soup.find_all("article"):
            name_tag = article.find("a", href=True)
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            magnet_tag = article.find("a", href=lambda x: x and x.startswith("magnet:"))
            magnet = magnet_tag["href"] if magnet_tag else ""
            results.append({
                "name": name,
                "magnet": magnet,
                "size": "",
                "seed": "",
                "leech": "",
                "date": "",
                "source": "TorLock"
            })
        time.sleep(random.uniform(*DELAY_RANGE))
    except Exception as e:
        print(f"  ❌ TorLock 失败: {e}")
    return results

def scrape_glodls(query):
    """Glodls (https://glodls.to)"""
    results = []
    try:
        url = f"https://glodls.to/search/{quote(query)}/"
        resp = safe_request(url)
        if not resp:
            return results
        soup = BeautifulSoup(resp.text, "html.parser")
        for row in soup.find_all("tr"):
            name_tag = row.find("a", class_="torrent-name")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            magnet_tag = row.find("a", href=lambda x: x and x.startswith("magnet:"))
            magnet = magnet_tag["href"] if magnet_tag else ""
            results.append({
                "name": name,
                "magnet": magnet,
                "size": "",
                "seed": "",
                "leech": "",
                "date": "",
                "source": "Glodls"
            })
        time.sleep(random.uniform(*DELAY_RANGE))
    except Exception as e:
        print(f"  ❌ Glodls 失败: {e}")
    return results

def scrape_magnetdl(query):
    """MagnetDL (https://magnetdl.com)"""
    results = []
    try:
        url = f"https://www.magnetdl.com/search/?m=1&q={quote(query)}"
        resp = safe_request(url)
        if not resp:
            return results
        soup = BeautifulSoup(resp.text, "html.parser")
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            name_tag = cells[1].find("a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            magnet_tag = row.find("a", href=lambda x: x and x.startswith("magnet:"))
            magnet = magnet_tag["href"] if magnet_tag else ""
            results.append({
                "name": name,
                "magnet": magnet,
                "size": "",
                "seed": "",
                "leech": "",
                "date": "",
                "source": "MagnetDL"
            })
        time.sleep(random.uniform(*DELAY_RANGE))
    except Exception as e:
        print(f"  ❌ MagnetDL 失败: {e}")
    return results

# ================== 超大规模多语言关键词（含成人，仅供学习） ==================
KEYWORDS = [
    # ---------- 中文 ----------
    "电影", "电视剧", "动画", "纪录片", "综艺", "音乐", "游戏", "软件", "电子书", "教程",
    "复仇者联盟", "阿凡达", "哪吒", "盗梦空间", "星际穿越", "蝙蝠侠", "蜘蛛侠", "钢铁侠",
    "美国队长", "雷神", "银河护卫队", "奇异博士", "黑豹", "惊奇队长", "蚁人", "毒液",
    "死侍", "金刚狼", "X战警", "神奇女侠", "海王", "沙丘", "信条", "小丑", "寄生虫",
    "权力的游戏", "绝命毒师", "风骚律师", "怪奇物语", "黑镜", "浴血黑帮", "曼达洛人",
    "进击的巨人", "鬼灭之刃", "咒术回战", "电锯人", "间谍过家家", "海贼王", "火影忍者",
    "死神", "龙珠", "我的英雄学院", "钢之炼金术师", "星际牛仔", "死亡笔记", "一拳超人",
    "三体", "流浪地球", "哈利波特", "指环王", "霍比特人", "星球大战", "变形金刚",
    "哥斯拉", "金刚", "环太平洋", "明日边缘", "源代码", "禁闭岛", "奥本海默",
    "芭比", "小美人鱼", "狮子王", "冰雪奇缘", "疯狂动物城", "寻梦环游记",
    "玩具总动员", "赛车总动员", "海底总动员", "超人总动员", "头脑特工队",
    "青春变形记", "魔法满屋", "夏日友晴天", "心灵奇旅", "疯狂原始人", "驯龙高手",
    "功夫熊猫", "冰川时代", "马达加斯加", "怪物史瑞克", "神偷奶爸", "小黄人",
    "爱宠大机密", "欢乐好声音", "大侦探福尔摩斯", "大侦探皮卡丘",
    "东方快车谋杀案", "尼罗河上的惨案", "金田一少年事件簿", "齐木楠雄的灾难",
    "辉夜大小姐", "棋魂", "中华小当家", "数码宝贝", "宝可梦", "名侦探柯南",
    "灌篮高手", "足球小将", "棒球英豪", "荒野求生", "地球脉动", "蓝色星球",
    "宇宙时空之旅", "宇宙的奇迹", "我们的星球", "王朝", "七个世界一个星球",
    "美丽中国", "生命", "人类星球", "非洲", "冰冻星球",
    "魔兽世界", "英雄联盟", "王者荣耀", "和平精英", "原神", "崩坏", "星穹铁道",
    "永劫无间", "幻兽帕鲁", "暗黑破坏神", "星际争霸", "炉石传说", "守望先锋",
    "APEX英雄", "泰坦陨落", "战锤", "全面战争", "文明", "三国志", "真三国无双",
    "无双大蛇", "战国无双", "使命召唤", "战地", "孤岛惊魂", "刺客信条", "古墓丽影",
    "生化危机", "最终幻想", "塞尔达", "马里奥", "动物森友会", "我的世界",
    "周杰伦", "林俊杰", "邓紫棋", "陈奕迅", "Taylor Swift", "Adele", "Ed Sheeran",
    "BTS", "Blackpink", "EXO", "Big Bang", "Coldplay", "Maroon 5", "Imagine Dragons",
    "Linkin Park", "Metallica", "Nirvana", "Queen", "The Beatles", "Michael Jackson",
    "Madonna", "Mariah Carey", "Whitney Houston", "Celine Dion", "Shakira",
    "Lady Gaga", "Katy Perry", "Rihanna", "Drake", "Kendrick Lamar", "Eminem",
    "Snoop Dogg", "Dr Dre", "50 Cent", "Jay-Z", "Kanye West", "Travis Scott",
    "Post Malone", "Billie Eilish", "Ariana Grande", "Justin Bieber", "Selena Gomez",
    "Miley Cyrus", "Dua Lipa", "Olivia Rodrigo", "Doja Cat", "Megan Thee Stallion",
    "Cardi B", "Nicki Minaj", "Lizzo", "SZA", "Frank Ocean", "Tyler, the Creator",
    "Childish Gambino", "Anderson .Paak", "Bruno Mars", "Sam Smith", "John Legend",
    "Alicia Keys", "Beyoncé",
    # ---------- 英文 ----------
    "movie", "film", "TV series", "anime", "documentary", "music", "game", "software", "ebook", "tutorial",
    "Avengers", "Avatar", "Inception", "Interstellar", "Batman", "Spider-Man", "Iron Man",
    "Captain America", "Thor", "Guardians of the Galaxy", "Doctor Strange", "Black Panther",
    "Captain Marvel", "Ant-Man", "Venom", "Deadpool", "Wolverine", "X-Men", "Wonder Woman",
    "Aquaman", "Dune", "Tenet", "Joker", "Parasite", "The Irishman", "Once Upon a Time in Hollywood",
    "Titanic", "Forrest Gump", "The Shawshank Redemption", "The Godfather", "Pulp Fiction",
    "Fight Club", "The Dark Knight", "Lord of the Rings", "The Hobbit", "Harry Potter",
    "Star Wars", "Transformers", "Fast and Furious", "Mission Impossible", "James Bond",
    "Jurassic World", "Godzilla", "Kong", "Pacific Rim", "Edge of Tomorrow", "Source Code",
    "Shutter Island", "The Prestige", "Memento", "Dunkirk", "Oppenheimer",
    "Barbie", "The Little Mermaid", "The Lion King", "Mulan", "Aladdin", "Beauty and the Beast",
    "Frozen", "Zootopia", "Coco", "Up", "Toy Story", "Cars", "Finding Nemo", "The Incredibles",
    "Inside Out", "Turning Red", "Encanto", "Luca", "Soul", "The Croods", "How to Train Your Dragon",
    "Kung Fu Panda", "Ice Age", "Madagascar", "Shrek", "Despicable Me", "Minions",
    "The Secret Life of Pets", "Sing", "Sherlock Holmes", "Detective Pikachu",
    "Murder on the Orient Express", "Death on the Nile", "Evil Under the Sun", "The ABC Murders",
    "Game of Thrones", "House of the Dragon", "Breaking Bad", "Better Call Saul",
    "Stranger Things", "Black Mirror", "Peaky Blinders", "The Mandalorian", "Ahsoka",
    "The Book of Boba Fett", "Obi-Wan Kenobi", "Andor", "Star Trek", "The Last of Us",
    "Succession", "The Bear", "Wednesday", "The Morning Show", "Ted Lasso", "Fleabag",
    "Killing Eve", "Chernobyl", "Band of Brothers", "The Pacific", "Fargo", "True Detective",
    "Westworld", "The Handmaid's Tale", "Big Little Lies", "Mare of Easttown",
    "The White Lotus", "Euphoria", "Industry", "Narcos", "Ozark", "House of Cards",
    "Orange Is the New Black", "The Witcher", "Vikings", "The Crown", "The Queen",
    "The Tudors", "Rome", "Spartacus", "Yellowstone", "1923", "1883", "Mayor of Kingstown",
    "Tulsa King", "NCIS", "Criminal Minds", "Sherlock", "Endeavour", "Vera",
    "Death in Paradise", "Father Brown", "Shetland", "Inspector George Gently",
    "Attack on Titan", "Demon Slayer", "Jujutsu Kaisen", "Chainsaw Man", "Spy x Family",
    "My Hero Academia", "Fullmetal Alchemist", "Cowboy Bebop", "Death Note", "One Punch Man",
    "Mob Psycho 100", "Vinland Saga", "Made in Abyss", "The Promised Neverland",
    "Tokyo Ghoul", "Re:Zero", "KonoSuba", "Overlord", "Sword Art Online",
    "The Rising of the Shield Hero", "Dr. Stone", "Tower of God", "Solo Leveling",
    "Frieren: Beyond Journey's End", "Oshi no Ko", "Bocchi the Rock", "Cyberpunk Edgerunners",
    "Arcane", "Hunter x Hunter", "Yu Yu Hakusho", "Slam Dunk", "Captain Tsubasa",
    "Touch", "Detective Conan", "Kindaichi Case Files", "The Disastrous Life of Saiki K.",
    "Kaguya-sama: Love Is War", "Hikaru no Go", "Cooking Master Boy", "Digimon", "Pokémon",
    "Planet Earth", "The Blue Planet", "Cosmos: A Spacetime Odyssey", "Wonders of the Universe",
    "Our Planet", "Horizon", "Frozen Planet", "Seven Worlds One Planet", "Dynasties",
    "The Mating Game", "Wild China", "Life", "Human Planet", "Africa", "Frozen Planet",
    "Wild Africa", "Wild Australia", "Earth Origins", "Planet Dinosaur", "Prehistoric Planet",
    "Underwater World", "Man vs. Wild", "Bear Grylls", "Survival", "The Deep", "The Universe",
    "Journey to the Edge of the Universe", "GTA", "Cyberpunk 2077", "Elden Ring",
    "Red Dead Redemption", "The Witcher 3", "The Elder Scrolls", "Fallout 4",
    "Call of Duty", "Battlefield", "Far Cry", "Assassin's Creed", "Tomb Raider",
    "Resident Evil", "Final Fantasy", "The Legend of Zelda", "Mario", "Animal Crossing",
    "Minecraft", "League of Legends", "Honor of Kings", "Game for Peace",
    "Genshin Impact", "Honkai", "Honkai: Star Rail", "Zenless Zone Zero",
    "Wuthering Waves", "Naraka: Bladepoint", "Palworld", "Diablo", "StarCraft",
    "Warcraft", "World of Warcraft", "Hearthstone", "Overwatch", "Destiny 2",
    "Apex Legends", "Titanfall", "Warhammer", "Total War", "Civilization",
    "Romance of the Three Kingdoms", "Dynasty Warriors", "Warriors Orochi",
    "Samurai Warriors", "Adobe", "Photoshop", "Premiere", "After Effects",
    "Audition", "Illustrator", "InDesign", "Lightroom", "Dreamweaver",
    "Flash", "Fireworks", "Office", "Word", "Excel", "PowerPoint",
    "Outlook", "Visio", "Project", "Windows", "Mac", "Linux",
    "Autocad", "3ds Max", "Maya", "Blender", "Unity", "Unreal",
    "Matlab", "Ansys", "SolidWorks", "Catia", "ProE", "UG", "NX",
    "Creo", "SOLIDWORKS", "Inventor", "Fusion 360", "Rhino", "SketchUp",
    "Revit", "Navisworks", "Civil 3D", "Tekla", "Bentley", "MicroStation",
    "MySQL", "Oracle", "SQL Server", "PostgreSQL", "MongoDB",
    "Visual Studio", "IntelliJ", "Eclipse", "PyCharm", "VSCode", "Node.js",
    "Python", "Java", "C++", "C#", "PHP", "Ruby", "Go", "Rust",
    "Swift", "Kotlin", "Dart", "Flutter", "React", "Angular",
    "Vue.js", "Spring", "Django", "Flask", "Tornado", "VMware",
    "VirtualBox", "Docker", "Kubernetes", "Jenkins", "Git", "SVN",
    "GitHub", "GitLab", "Bitbucket",
    # ---------- 日语 ----------
    "映画", "ドラマ", "アニメ", "漫画", "ゲーム", "音楽", "ソフトウェア",
    "進撃の巨人", "鬼滅の刃", "呪術廻戦", "チェンソーマン", "SPY×FAMILY",
    "ワンピース", "NARUTO", "BLEACH", "ドラゴンボール", "僕のヒーローアカデミア",
    "鋼の錬金術師", "カウボーイビバップ", "デスノート", "ワンパンマン",
    "モブサイコ100", "ヴィンランド・サガ", "メイドインアビス", "約束のネバーランド",
    "東京喰種", "リゼロ", "この素晴らしい世界に祝福を！", "オーバーロード",
    "ソードアート・オンライン", "盾の勇者の成り上がり", "Dr.STONE",
    "神の塔", "俺だけレベルアップ", "葬送のフリーレン", "推しの子",
    "ぼっち・ざ・ろっく！", "サイバーパンク エッジランナーズ", "アーケイン",
    "ハンター×ハンター", "幽☆遊☆白書", "スラムダンク", "キャプテン翼",
    "タッチ", "名探偵コナン", "金田一少年の事件簿", "斉木楠雄のΨ難",
    "かぐや様は告らせたい", "ヒカルの碁", "中華一番！", "デジモン", "ポケットモンスター",
    "千と千尋の神隠し", "君の名は。", "すずめの戸締まり", "天気の子",
    "もののけ姫", "風の谷のナウシカ", "天空の城ラピュタ", "となりのトトロ",
    "魔女の宅急便", "紅の豚", "海がきこえる", "平成狸合戦ぽんぽこ",
    "耳をすませば", "もののけ姫", "千と千尋の神隠し", "ハウルの動く城",
    "ゲド戦記", "崖の上のポニョ", "借りぐらしのアリエッティ", "コクリコ坂から",
    "風立ちぬ", "かぐや姫の物語", "思い出のマーニー",
    # ---------- 韩语 ----------
    "영화", "드라마", "애니메이션", "게임", "음악", "소프트웨어",
    "어벤져스", "아바타", "인셉션", "인터스텔라", "배트맨", "스파이더맨",
    "아이언맨", "캡틴 아메리카", "토르", "가디언즈 오브 갤럭시", "닥터 스트레인지",
    "블랙 팬서", "캡틴 마블", "앤트맨", "베놈", "데드풀", "울버린", "엑스맨",
    "원더우먼", "아쿠아맨", "듄", "테넷", "조커", "기생충", "아이리시맨",
    "타이타닉", "포레스트 검프", "쇼생크 탈출", "대부", "펄프 픽션", "파이트 클럽",
    "다크 나이트", "반지의 제왕", "호빗", "해리 포터", "스타워즈", "트랜스포머",
    "패스트 앤 퓨리어스", "미션 임파서블", "007", "쥬라기 월드", "고질라", "콩",
    "고질라 대 콩", "퍼시픽 림", "에지 오브 투모로우", "소스 코드", "셔터 아일랜드",
    "오펜하이머", "바비", "인어공주", "라이온 킹", "뮬란", "알라딘", "미녀와 야수",
    "겨울왕국", "주토피아", "코코", "업", "토이 스토리", "카", "니모를 찾아서",
    "인크레더블", "인사이드 아웃", "터닝 레드", "엔칸토", "루카", "소울",
    "크루즈 가족", "드래곤 길들이기", "쿵푸 팬더", "아이스 에이지", "마다가스카르",
    "슈렉", "슈퍼 배드", "미니언즈", "펫", "싱", "셜록 홈즈", "명탐정 피카츄",
    "오리엔트 특급 살인", "나일 강의 죽음", "태양 아래의 악", "ABC 살인사건",
    "왕좌의 게임", "하우스 오브 드래곤", "브레이킹 배드", "베터 콜 사울",
    "기묘한 이야기", "블랙 미러", "피키 블라인더스", "만달로리안", "아소카",
    "오비완 케노비", "앤도어", "스타 트렉", "라스트 오브 어스", "석세션",
    "더 베어", "웬즈데이", "모닝 쇼", "테드 래소", "플리백", "킬링 이브",
    "체르노빌", "밴드 오브 브라더스", "퍼시픽", "파고", "트루 디텍티브",
    "웨스트월드", "핸드메이즈 테일", "빅 리틀 라이즈", "메어 오브 이스트타운",
    "화이트 로터스", "유포리아", "인더스트리", "나르코스", "오자크", "하우스 오브 카드",
    "오렌지 이즈 더 뉴 블랙", "위쳐", "바이킹", "더 크라운", "여왕", "튜더스",
    "로마", "스파르타쿠스", "옐로스톤", "1923", "1883", "킹스타운 시장",
    "털사 킹", "NCIS", "크리미널 마인드", "셜록", "엔데버", "베라",
    "데스 인 파라다이스", "파더 브라운", "셰틀랜드", "조지 젠틀리 경감",
    "진격의 거인", "귀멸의 칼날", "주술회전", "체인소맨", "스파이 패밀리",
    "원피스", "나루토", "블리치", "드래곤볼", "나의 히어로 아카데미아",
    "강철의 연금술사", "카우보이 비밥", "데스노트", "원펀맨", "모브 사이코 100",
    "빈란드 사가", "메이드 인 어비스", "약속의 네버랜드", "도쿄 구울",
    "리제로", "이 멋진 세계에 축복을!", "오버로드", "소드 아트 온라인",
    "방패 용사 성공기", "Dr.STONE", "신의 탑", "나 혼자만 레벨업",
    "장송의 프리렌", "최애의 아이", "보치 더 록", "사이버펑크 엣지러너",
    "아케인", "헌터x헌터", "유유백서", "슬램덩크", "캡틴 츠바사",
    "터치", "명탐정 코난", "김전일", "사이키 쿠스오의 재난",
    "카구야 님은 고백받고 싶어", "히카루의 바둑", "중화일번", "디지몬", "포켓몬스터",
    # ---------- 成人内容（仅供技术学习，请遵守当地法律） ----------
    "porn", "xxx", "adult", "hentai", "jav", "sex", "nude", "nsfw", "18+",
    "アダルト", "成人", "成人电影", "成人视频", "成人动漫", "成人游戏", "成人写真",
    "jav", "japanese adult", "korean adult", "chinese adult", "欧美成人", "国产成人",
    "av", "japan av", "korea av", "china av", "成人影片", "成人网站",
    "onlyfans", "fansly", "patreon", "private", "leak", "uncensored",
    "无码", "有码", "中出", "制服", "丝袜", "足交", "肛交", "口交",
    "sm", "捆绑", "调教", "露出", "羞耻", "强奸", "轮奸", "乱伦", "熟女",
    "萝莉", "御姐", "正太", "伪娘", "人妖", "变性", "双性", "同性",
    "lesbian", "gay", "bisexual", "transgender", "queer", "lgbt",
    "cosplay", "角色扮演", "情趣", "内衣", "美腿", "丝足", "足控",
    "自慰", "手淫", "口爆", "颜射", "内射", "体外射精", "避孕",
    "情趣用品", "飞机杯", "震动棒", "跳蛋", "束缚带", "鞭子",
    "sm视频", "调教视频", "成人直播", "裸聊", "视频聊天", "裸照",
    "性爱", "做爱", "高潮", "阴蒂", "阴道", "阴茎", "睾丸", "精液",
    "月经", "更年期", "性病", "艾滋病", "安全套", "避孕药",
    # ========== 新增关键词（扩充至 500+） ==========
    "Top Gun Maverick", "Everything Everywhere All at Once", "The Whale", "Elvis",
    "The Batman", "Bullet Train", "Uncharted", "Sonic the Hedgehog", "Morbius",
    "Fantastic Beasts", "The Northman", "Ambulance", "The Lost City", "Downton Abbey",
    "Lightyear", "Minions The Rise of Gru", "Thor Love and Thunder", "Black Adam",
    "Smile", "The Menu", "Violent Night", "Babylon", "The Fabelmans", "Women Talking",
    "Tár", "Aftersun", "Decision to Leave", "RRR", "The Banshees of Inisherin",
    "Triangle of Sadness", "Glass Onion", "The Pale Blue Eye", "Knock at the Cabin",
    "Ant-Man and the Wasp Quantumania", "Creed III", "Scream VI", "John Wick Chapter 4",
    "The Super Mario Bros Movie", "Evil Dead Rise", "Guardians of the Galaxy Vol 3",
    "Fast X", "The Little Mermaid 2023", "Across the Spider-Verse", "Transformers Rise of the Beasts",
    "Elemental", "The Flash 2023", "Indiana Jones and the Dial of Destiny",
    "Mission Impossible Dead Reckoning", "Oppenheimer 2023", "Barbie 2023",
    "Teenage Mutant Ninja Turtles", "Blue Beetle", "Gran Turismo", "The Equalizer 3",
    "The Nun II", "A Haunting in Venice", "The Creator", "Saw X", "The Exorcist Believer",
    "Killers of the Flower Moon", "Five Nights at Freddy's", "The Marvels",
    "The Hunger Games Ballad of Songbirds", "Wish 2023", "Napoleon 2023", "Aquaman 2",
    "Wonka 2023", "The Color Purple 2023", "Migration", "Ferrari", "Poor Things 2023",
    "Anyone But You", "The Iron Claw", "The Beekeeper", "Mean Girls 2024",
    "Dune Part Two 2024", "Kung Fu Panda 4", "Ghostbusters Frozen Empire",
    "Godzilla x Kong The New Empire", "Civil War 2024", "Abigail 2024",
    "Challengers 2024", "The Fall Guy 2024", "Kingdom of the Planet of the Apes",
    "Furiosa", "Bad Boys Ride or Die", "Inside Out 2 2024", "A Quiet Place Day One",
    "Despicable Me 4 2024", "Twisters 2024", "Deadpool and Wolverine", "Alien Romulus",
    "Borderlands 2024", "Beetlejuice 2", "Joker Folie à Deux", "Venom 3",
    "Gladiator 2", "Wicked", "Moana 2", "Sonic 3", "Mufasa The Lion King",
    "The Matrix 4", "John Wick 3", "Mission Impossible Fallout", "Avengers Endgame",
    "Avengers Infinity War", "Captain America Civil War", "Thor Ragnarok",
    "Guardians of the Galaxy Vol 2", "Doctor Strange", "Spider-Man Homecoming",
    "Spider-Man Far From Home", "Spider-Man No Way Home", "Black Panther Wakanda Forever",
    "Shang-Chi", "Eternals", "Black Widow", "Captain Marvel", "Ant-Man and the Wasp",
    "Deadpool 2", "Logan", "The Wolverine", "X-Men First Class", "X-Men Days of Future Past",
    "X-Men Apocalypse", "Dark Phoenix", "Star Wars The Force Awakens", "Rogue One",
    "The Last Jedi", "Solo", "The Rise of Skywalker", "Mad Max Fury Road",
    "Jurassic World", "Fallen Kingdom", "Dominion", "Godzilla 2014", "King of the Monsters",
    "Godzilla vs Kong", "Skull Island", "Pacific Rim Uprising", "The Meg", "The Meg 2",
    "Avatar The Way of Water", "Avatar 3", "Titanic 3D", "Terminator Dark Fate",
    "Terminator Genisys", "Predator 2018", "Alien Covenant", "Alien Prometheus",
    "The Matrix Resurrections", "The Matrix Reloaded", "The Matrix Revolutions",
    "Fight Club", "Seven", "The Game", "Zodiac", "Gone Girl", "The Social Network",
    "The Girl with the Dragon Tattoo", "The Curious Case of Benjamin Button",
    "Arrival", "Blade Runner 2049", "Sicario", "Prisoners", "Enemy", "Incendies",
    "Whiplash", "La La Land", "First Man", "Babylon 2022",
    "Toy Story 4", "Toy Story 3", "Toy Story 2", "Monsters Inc", "Ratatouille",
    "WALL-E", "The Incredibles 2", "Brave", "Onward", "Coco", "Inside Out 2",
    "Elemental 2023", "Elio", "How to Train Your Dragon 3", "The Hidden World",
    "Kung Fu Panda 3", "Shrek Forever After", "Puss in Boots The Last Wish",
    "The Croods 2", "The Boss Baby", "Trolls", "Trolls Band Together",
    "Migration 2023", "The Bad Guys", "Minions The Rise of Gru", "Sing 2",
    "Inception 4K", "Interstellar 4K", "The Dark Knight 4K", "Dunkirk 4K",
    "Tenet 4K", "Oppenheimer 4K", "Dune 2021 4K", "Dune Part Two 4K",
    "Blade Runner 2049 4K", "1917 4K", "Mad Max Fury Road 4K", "Joker 4K",
    "Parasite 4K", "The Revenant 4K", "Gravity 4K", "The Martian 4K",
    "Arrival 4K", "La La Land 4K", "Whiplash 4K", "Baby Driver 4K",
    "Fury 4K", "Hacksaw Ridge 4K", "Saving Private Ryan 4K", "Schindler 4K",
    "The Pianist 4K", "Apocalypse Now 4K", "Full Metal Jacket 4K", "Platoon 4K",
    "Gladiator 4K", "Braveheart 4K", "The Patriot 4K", "Troy 4K",
    "300 4K", "Kingdom of Heaven 4K", "The Last Samurai 4K", "Mulan 2020 4K",
    "Crouching Tiger Hidden Dragon 4K", "Hero 4K", "House of Flying Daggers 4K",
    "The Grandmaster 4K", "Ip Man 4K", "Enter the Dragon 4K", "The Raid 4K",
    "The Raid 2 4K", "John Wick 4K", "John Wick 2 4K", "John Wick 3 4K",
    "Nobody 4K", "Atomic Blonde 4K", "The Bourne Identity 4K", "Bourne Supremacy 4K",
    "Bourne Ultimatum 4K", "Jason Bourne 4K", "Casino Royale 4K", "Skyfall 4K",
    "Spectre 4K", "No Time to Die 4K", "Mission Impossible 1 4K", "MI 2 4K",
    "MI 3 4K", "MI Ghost Protocol 4K", "MI Rogue Nation 4K", "MI Fallout 4K",
    "Die Hard 4K", "Die Hard 2 4K", "Die Hard with a Vengeance 4K", "Speed 4K",
    "The Terminator 4K", "Terminator 2 4K", "Predator 4K", "RoboCop 4K",
    "Total Recall 4K", "Starship Troopers 4K", "Independence Day 4K", "Men in Black 4K",
    "Jurassic Park 4K", "The Lost World Jurassic Park 4K", "JP3 4K", "E.T. 4K",
    "Close Encounters 4K", "Back to the Future 4K", "BTTF 2 4K", "BTTF 3 4K",
    "Ghostbusters 1984 4K", "Ghostbusters 2 4K", "The Goonies 4K", "Gremlins 4K",
    "Indiana Jones 4K", "Temple of Doom 4K", "Last Crusade 4K", "Raiders 4K",
    "The Rock 4K", "Con Air 4K", "Face-Off 4K", "Broken Arrow 4K", "True Lies 4K",
    "Jingle All the Way 4K", "Home Alone 4K", "Home Alone 2 4K", "Elf 4K",
    "The Grinch 4K", "The Polar Express 4K", "Nightmare Before Christmas 4K",
    "Mean Girls 2004 4K", "Clueless 4K", "Legally Blonde 4K", "Bridesmaids 4K",
    "Pitch Perfect 4K", "Easy A 4K", "Superbad 4K", "The Hangover 4K",
    "Step Brothers 4K", "Anchorman 4K", "Dumb and Dumber 4K", "Ace Ventura 4K",
    "The Mask 4K", "Bruce Almighty 4K", "Liar Liar 4K", "Patch Adams 4K",
    "American Pie 4K", "Scary Movie 4K", "Not Another Teen Movie 4K", "10 Things I Hate About You 4K",
    "She's All That 4K", "Never Been Kissed 4K", "The Proposal 4K", "The Devil Wears Prada 4K",
    "Pretty Woman 4K", "My Best Friend's Wedding 4K", "Notting Hill 4K", "Love Actually 4K",
    "Four Weddings and a Funeral 4K", "Bridget Jones 4K", "About Time 4K", "The Time Traveler's Wife 4K",
    "Eternal Sunshine 4K", "Her 4K", "Lost in Translation 4K", "Moonrise Kingdom 4K",
    "The Grand Budapest Hotel 4K", "The Darjeeling Limited 4K", "The Life Aquatic 4K",
    "The Royal Tenenbaums 4K", "Rushmore 4K", "Fantastic Mr Fox 4K", "Isle of Dogs 4K",
    "The French Dispatch 4K", "Asteroid City 4K", "The Shape of Water 4K",
    "Pan's Labyrinth 4K", "Hellboy 4K", "Hellboy 2 4K", "Pacific Rim 4K",
    "Crimson Peak 4K", "The Devil's Backbone 4K", "Kubo and the Two Strings 4K",
    "ParaNorman 4K", "Coraline 4K", "The Boxtrolls 4K", "Missing Link 4K",
    "Wendell and Wild 4K", "Guillermo del Toro's Pinocchio 4K", "Spider-Man Into the Spider-Verse 4K",
    "The Lego Movie 4K", "The Lego Batman Movie 4K", "Lego Ninjago 4K", "Lego Movie 2 4K",
    "Megamind 4K", "Monsters vs Aliens 4K", "Shark Tale 4K", "Shrek 2 4K", "Shrek 3 4K",
    "Over the Hedge 4K", "Flushed Away 4K", "Bee Movie 4K", "Rango 4K",
    "The Adventures of Tintin 4K", "A Scanner Darkly 4K", "Waking Life 4K",
    "Scanner Darkly 4K", "Paprika 4K", "Perfect Blue 4K", "Millennium Actress 4K",
    "Tokyo Godfathers 4K", "Akira 4K", "Ghost in the Shell 4K", "Ghost in the Shell 2 4K",
    "Ninja Scroll 4K", "Vampire Hunter D Bloodlust 4K", "Redline 4K",
    "Summer Wars 4K", "The Girl Who Leapt Through Time 4K", "Wolf Children 4K",
    "The Boy and the Beast 4K", "Mirai 4K", "Belle 4K", "Weathering with You 4K",
    "Suzume 4K", "Your Name 4K", "5 Centimeters per Second 4K", "The Garden of Words 4K",
    "A Silent Voice 4K", "I Want to Eat Your Pancreas 4K", "Josee the Tiger and the Fish 4K",
    "Ride Your Wave 4K", "Maquia 4K", "Violet Evergarden 4K", "Bubble 4K",
    "Words Bubble Up Like Soda Pop 4K", "A Whisker Away 4K", "Lu Over the Wall 4K",
    "Inu-Oh 4K", "Modest Heroes 4K", "Mary and The Witch's Flower 4K", "Penguin Highway 4K",
    "Fireworks 4K", "Flavors of Youth 4K", "Hello World 4K", "Promare 4K",
    "Mekakucity Actors 4K", "Kimi ni Todoke 4K", "Orange 4K", "Anohana 4K",
    "Clannad 4K", "Angel Beats 4K", "Charlotte 4K", "Plastic Memories 4K",
    "Your Lie in April 4K", "Hyouka 4K", "Toradora 4K", "Golden Time 4K",
    "Sakurasou 4K", "Chuunibyou 4K", "K-On 4K", "Haruhi Suzumiya 4K",
    "Lucky Star 4K", "Nichijou 4K", "Daily Lives of High School Boys 4K",
    "Gintama 4K", "JoJo's Bizarre Adventure 4K", "Fate/zero 4K", "Fate/stay night UBW 4K",
    "Fate/Apocrypha 4K", "Fate/Extra 4K", "Demon Slayer Mugen Train 4K", "Demon Slayer Infinity Castle 4K",
    "Jujutsu Kaisen 0 4K", "Chainsaw Man Movie 4K", "Attack on Titan Final Season 4K",
    "Attack on Titan The Final Chapters 4K", "One Piece Film Red 4K", "One Piece Film Gold 4K",
    "One Piece Film Z 4K", "One Piece Strong World 4K", "Dragon Ball Super Broly 4K",
    "Dragon Ball Super Super Hero 4K", "My Hero Academia Heroes Rising 4K",
    "My Hero Academia World Heroes Mission 4K", "Black Clover Sword of the Wizard King 4K",
    "Sword Art Online Ordinal Scale 4K", "Sword Art Online Progressive 4K",
    "SAO Progressive Scherzo 4K", "The Quintessential Quintuplets Movie 4K",
    "Fate/stay night Heaven's Feel 4K", "Fate/Grand Order Camelot 4K",
    "Fate/Grand Order Babylonia 4K", "Fate/Grand Order Solomon 4K",
    "Evangelion 4K", "End of Evangelion 4K", "Evangelion 3.0+1.0 4K", "Rebuild of Evangelion 4K",
    "Macross Frontier 4K", "Macross Delta 4K", "Gundam Hathaway 4K", "Gundam NT 4K",
    "Gundam Unicorn 4K", "Gundam The Origin 4K", "Code Geass Lelouch of the Resurrection 4K",
    "Code Geass Akito the Exiled 4K", "Legend of the Galactic Heroes 4K",
    "A Certain Magical Index 4K", "A Certain Scientific Railgun 4K", "Toaru Series 4K",
    "Monogatari Series 4K", "Bakemonogatari 4K", "Nisemonogatari 4K", "Nekomonogatari 4K",
    "Owarimonogatari 4K", "Puella Magi Madoka Magica 4K", "Madoka Rebellion 4K",
    "Steins Gate 4K", "Steins Gate 0 4K", "Re Zero Memory Snow 4K", "Re Zero Frozen Bonds 4K",
    "Mushoku Tensei 4K", "That Time I Got Reincarnated as a Slime 4K", "Tensura Movie 4K",
    "No Game No Life Zero 4K", "Overlord Movie 4K", "Konosuba Movie 4K", "Konosuba Legend of Crimson 4K",
    "The Rising of the Shield Hero 4K", "Shield Hero Season 2 4K", "Shield Hero Season 3 4K",
    "Dr Stone Ryusui 4K", "Dr Stone New World 4K", "Mob Psycho 100 III 4K",
    "One Punch Man Season 2 4K", "One Punch Man Season 3 4K", "Tokyo Revengers 4K",
    "Spy x Family Movie Code White 4K", "Solo Leveling Movie 4K", "Oshi no Ko Movie 4K"
    # 更多可自行补充
]

# ================== 爬取聚合 ==================

def fetch_all(query):
    """对单个关键词，并发调用所有已实现的爬虫"""
    all_results = []
    scraper_funcs = [
        scrape_btdigg,
        scrape_piratebay,
        scrape_1337x,
        scrape_yts,
        scrape_eztv,
        scrape_limetorrents,
        scrape_torrent9,
        scrape_nyaa,
        scrape_dmhy,
        scrape_skrbt,
        scrape_torrentgalaxy,
        scrape_torlock,
        scrape_glodls,
        scrape_magnetdl,
    ]
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(scraper_funcs))) as executor:
        future_to_scraper = {executor.submit(func, query): func.__name__ for func in scraper_funcs}
        for future in as_completed(future_to_scraper):
            name = future_to_scraper[future]
            try:
                res = future.result()
                all_results.extend(res)
                print(f"  ✅ {name} 获得 {len(res)} 条")
            except Exception as e:
                print(f"  ❌ {name} 异常: {e}")
    return all_results

# ================== 智能去重 ==================

def is_similar(a, b, threshold=SIMILARITY_THRESHOLD):
    """判断两个字符串是否相似（忽略大小写）"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() > threshold

def deduplicate(data):
    """去重：先按磁力链前40字符，再按名称相似度"""
    seen_hashes = set()
    unique = []
    for item in data:
        magnet = item.get("magnet", "")
        if not magnet:
            continue
        hash_key = magnet[:40]
        if hash_key in seen_hashes:
            continue
        # 检查名称是否与已存在条目相似
        dup = False
        for existing in unique:
            if is_similar(item["name"], existing["name"]):
                dup = True
                break
        if not dup:
            seen_hashes.add(hash_key)
            unique.append(item)
    return unique

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

    # 写入 data.js
    with open("data.js", "w", encoding="utf-8") as f:
        f.write("window.MAGNET_DATA = " + json.dumps(unique_data, ensure_ascii=False, indent=2) + ";")

    print(f"\n✅ 全部完成！共 {len(unique_data)} 条磁力链接")

if __name__ == "__main__":
    main()
