Title: fix: robust parse for data.js in index.html; minify data.js output in crawler.py

This pull request makes the frontend parsing of data.js more robust and the crawler output more compact:

- Fix: index.html now strips the `window.MAGNET_DATA` prefix and trailing semicolon before parsing, and falls back to a cross-line regex if necessary. It also shows clear status messages on parsing failures.
- Fix: crawler.py now writes `data.js` as minified JSON (no pretty indentation) to ensure compatibility with various parsing strategies and reduce file size.

Why:
- Previously the frontend used a regex that didn't match multi-line JSON (pretty-printed), causing the page to show no data. These changes ensure reliable parsing whether data.js is pretty-printed or minified.

How to test:
1. Run the crawler: `python3 crawler.py` to regenerate data.js
2. Serve the repo locally: `python3 -m http.server 8000` and open `http://localhost:8000`
3. Confirm the page loads data and displays the number of items.

If you'd like a smaller data.js, consider gzipping in CI or trimming the KEYWORDS list to reduce data volume.
