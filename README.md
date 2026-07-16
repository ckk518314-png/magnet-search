# 🧲 磁力搜索 (Magnet Search)

一个纯静态的磁力搜索 Web 应用,部署在 GitHub Pages 上。

## 特性
- 🔍 实时搜索全网磁力资源
- 📱 iOS 友好,支持添加到主屏幕
- ⚡ 纯静态,加载快
- 🔄 GitHub Actions 每日自动抓取新资源

## 在线访问
👉 https://ckk518314-png.github.io/magnet-search/

## 数据源
由 `crawler.py` 每日自动从 11 个 BT 源抓取:
- BTDigg, 海盗湾, 1337x, YTS, EZTV
- LimeTorrents, Torrent9, Nyaa
- 动漫花园, SkrBT

## 部署
- 前端:`index.html` + `data.js`
- 后端爬虫:`crawler.py` (GitHub Actions 每日 0:00 UTC 运行)
- 静态托管:GitHub Pages
