from http.server import HTTPServer, BaseHTTPRequestHandler
from os import path
from urllib.parse import urlparse, parse_qs
import re
import time
import os
import json
import html
from datetime import datetime

import urllib.request
import urllib.parse
import html
import re

import csv

PORT = 8080

# ============================================================
# DIRECTORY & PATH SETUP (مدیریت پوشه‌ها و مسیرها)
# ============================================================
DATA_DIR = "data"
CATEGORIES_DIR = os.path.join(DATA_DIR, "categories")
TEMP_DIR = os.path.join(DATA_DIR, "temp")

# ساخت خودکار پوشه‌ها در صورت عدم وجود
os.makedirs(CATEGORIES_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

BLACKLIST_FILE = os.path.join(DATA_DIR, "blacklist.json")
COUNTRY_KEYWORDS_FILE = os.path.join(DATA_DIR, "country_keywords.json")
UNDO_HISTORY_FILE = os.path.join(TEMP_DIR, "undo_history.json")

# ============================================================
# STORAGE HELPERS
# ============================================================

def load_blacklist():
    if os.path.exists(BLACKLIST_FILE):
        try:
            with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_blacklist(blacklist_set):
    try:
        with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(list(blacklist_set), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving blacklist: {e}")

def load_undo_history():
    if os.path.exists(UNDO_HISTORY_FILE):
        try:
            with open(UNDO_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_undo_history(history):
    try:
        with open(UNDO_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving undo history: {e}")

def load_country_keywords():
    if os.path.exists(COUNTRY_KEYWORDS_FILE):
        try:
            with open(COUNTRY_KEYWORDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_country_keywords(data):
    try:
        with open(COUNTRY_KEYWORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving country keywords: {e}")

def get_category_files(category):
    safe_cat = re.sub(r'[^a-zA-Z0-9_-]', '_', category.strip().lower())
    return {
        "unreviewed_json": os.path.join(CATEGORIES_DIR, f"unreviewed_{safe_cat}.json"),
        "reviewed_json": os.path.join(CATEGORIES_DIR, f"reviewed_{safe_cat}.json"),
        "csv": os.path.join(CATEGORIES_DIR, f"groups_{safe_cat}.csv")
    }

def load_category_data(category):
    files = get_category_files(category)
    unreviewed = []
    reviewed = []
    
    if os.path.exists(files["unreviewed_json"]):
        try:
            with open(files["unreviewed_json"], "r", encoding="utf-8") as f:
                unreviewed = json.load(f)
        except Exception:
            pass

    if os.path.exists(files["reviewed_json"]):
        try:
            with open(files["reviewed_json"], "r", encoding="utf-8") as f:
                reviewed = json.load(f)
        except Exception:
            pass

    return unreviewed, reviewed

import csv

def save_category_data(category, unreviewed, reviewed):
    files = get_category_files(category)
    with open(files["unreviewed_json"], "w", encoding="utf-8") as f:
        json.dump(unreviewed, f, ensure_ascii=False, indent=2)

    with open(files["reviewed_json"], "w", encoding="utf-8") as f:
        json.dump(reviewed, f, ensure_ascii=False, indent=2)

    # ایجاد فایل خروجی CSV بدون نیاز به pandas و با کتابخانه پیش‌فرض پایتون
    all_rows = []
    for item in reviewed:
        all_rows.append({
            "name": item.get("name", ""),
            "url": item.get("url", ""),
            "description": item.get("description", ""),
            "category": category,
            "status": "reviewed"
        })
    
    if all_rows:
        try:
            with open(files["csv"], "w", encoding="utf-8-sig", newline="") as csvfile:
                fieldnames = ["name", "url", "description", "category", "status"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row in all_rows:
                    writer.writerow(row)
        except Exception as e:
            print(f"Error saving CSV: {e}")
# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_text(text):
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def normalize_url(url):
    if not url:
        return ""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    m = re.search(r'(https?://(?:www\.)?facebook\.com/groups/[^/?#]+)', url, re.IGNORECASE)
    if m:
        return m.group(1).rstrip("/") + "/"
    parsed = urlparse(url)
    return f"https://{parsed.netloc.lower()}{parsed.path.rstrip('/')}/"

def extract_group_slug(url):
    if not url:
        return None
    m = re.search(r"facebook\.com/groups/([^/?#]+)", url, re.IGNORECASE)
    return m.group(1) if m else None

# ============================================================
# SEARCH ENGINE
# ============================================================

class SearchAnalyzer:
    def __init__(self):
        pass

    def search(self, query, max_results=30, retries=3):
        for attempt in range(retries):
            try:
                print(f"    [SEARCH ENGINE] 🔍 Querying DuckDuckGo HTML (Attempt {attempt+1}): '{query}'")
                url = "https://html.duckduckgo.com/html/"
                data = urllib.parse.urlencode({'q': query}).encode('utf-8')
                req = urllib.request.Request(
                    url, 
                    data=data, 
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                )
                
                with urllib.request.urlopen(req, timeout=10) as response:
                    html_content = response.read().decode('utf-8')
                
                results = []
                match_urls = re.findall(r'class="result__url"[^>]*href="([^"]+)"', html_content)
                match_titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html_content, re.DOTALL)
                match_snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html_content, re.DOTALL)
                
                for i in range(min(len(match_urls), max_results)):
                    u = match_urls[i]
                    if 'uddg=' in u:
                        parsed_u = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
                        if 'uddg' in parsed_u:
                            u = parsed_u['uddg'][0]
                    
                    t = re.sub(r'<.*?>', '', match_titles[i]) if i < len(match_titles) else ""
                    s = re.sub(r'<.*?>', '', match_snippets[i]) if i < len(match_snippets) else ""
                    
                    results.append({
                        "href": u,
                        "title": html.unescape(t.strip()),
                        "body": html.unescape(s.strip())
                    })
                return results
            except Exception as e:
                print(f"    [SEARCH ENGINE] ❌ Search error (attempt {attempt+1}): {e}")
                if attempt < retries - 1:
                    time.sleep(2)
                else:
                    return []
        return []

def search_groups_logic(include_kws, category):
        blacklist = load_blacklist()
        
        # تغییر کلیدی: جمع‌آوری تمام لینک‌های موجود در *تمامی* دسته‌بندی‌ها
        existing_urls = set()
        if os.path.exists(CATEGORIES_DIR):
            for filename in os.listdir(CATEGORIES_DIR):
                if filename.endswith(".json"):
                    file_path = os.path.join(CATEGORIES_DIR, filename)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            items = json.load(f)
                            if isinstance(items, list):
                                for item in items:
                                    if "url" in item:
                                        existing_urls.add(normalize_url(item["url"]))
                    except Exception:
                        pass

        # بارگذاری داده‌های دسته‌بندی فعلی برای اضافه کردن نتایج جدید به آن
        unreviewed, reviewed = load_category_data(category)
        
        discovered = {}
        searcher = SearchAnalyzer()

        queries = [f"site:facebook.com/groups/ {kw.strip()}" for kw in include_kws if kw.strip()]

        for query in queries:
            print(f"\n[DISCOVERY QUERY] {query}")
            results = searcher.search(query, 30)
            for result in results:
                url = result.get("href") or result.get("link") or ""
                if not url or "facebook.com/groups" not in url.lower():
                    continue
                slug = extract_group_slug(url)
                if not slug or slug.lower() in ["search", "posts", "user", "sharer", "profile", "feed", "discover"]:
                    continue
                
                clean_url = normalize_url(url)
                # بررسی اینکه آیا لینک در لیست سیاه یا هر دسته‌بندی دیگری وجود دارد یا خیر
                if clean_url in blacklist or clean_url in existing_urls:
                    continue

                if clean_url not in discovered:
                    discovered[clean_url] = {
                        "title": clean_text(result.get("title", "")),
                        "snippet": clean_text(result.get("body") or result.get("snippet") or "")
                    }
            time.sleep(0.2)

        new_items = []
        for url, info in discovered.items():
            new_items.append({
                "url": url,
                "slug": extract_group_slug(url),
                "name": info["title"] or "Not Found",
                "description": info["snippet"] or "Not Found",
                "category": category,
                "analyzed_at": datetime.utcnow().isoformat()
            })

        unreviewed.extend(new_items)
        save_category_data(category, unreviewed, reviewed)
        return {"unreviewed": unreviewed, "reviewed": reviewed}
# ============================================================
# HTTP SERVER & API
# ============================================================

class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)

        if path == "/get-countries":
            all_kw = load_country_keywords()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"countries": list(all_kw.keys())}, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/get-data":
            category = query_params.get("category", [""])[0].strip().lower()
            all_kw = load_country_keywords()
            kws = all_kw.get(category, [])
            unreviewed, reviewed = load_category_data(category) if category else ([], [])
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"keywords": kws, "unreviewed": unreviewed, "reviewed": reviewed}, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/save-keywords":
            category = query_params.get("category", [""])[0].strip().lower()
            keywords_str = query_params.get("keywords", [""])[0]
            kws = [k.strip() for k in keywords_str.split(",") if k.strip()]
            if category:
                all_kw = load_country_keywords()
                all_kw[category] = kws
                save_country_keywords(all_kw)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/search":
            category = query_params.get("category", [""])[0].strip().lower()
            inc_str = query_params.get("include", [""])[0]
            
            # اصلاح این قسمت برای پشتیبانی از کامای انگلیسی و فارسی (،)
            inc_kws = [k.strip() for k in re.split(r'[,،]', inc_str) if k.strip()]
            
            data = search_groups_logic(inc_kws, category)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
            return

        if path == "/block":
            url_to_block = query_params.get("url", [""])[0]
            category = query_params.get("category", [""])[0].strip().lower()
            if url_to_block:
                clean_url = normalize_url(url_to_block)
                blacklist = load_blacklist()
                blacklist.add(clean_url)
                save_blacklist(blacklist)

                unreviewed, reviewed = load_category_data(category)
                removed_item = None
                
                new_unreviewed = []
                for item in unreviewed:
                    if normalize_url(item["url"]) == clean_url:
                        removed_item = {"item": item, "list_type": "unreviewed", "category": category}
                    else:
                        new_unreviewed.append(item)

                new_reviewed = []
                for item in reviewed:
                    if normalize_url(item["url"]) == clean_url:
                        removed_item = {"item": item, "list_type": "reviewed", "category": category}
                    else:
                        new_reviewed.append(item)

                if removed_item:
                    history = load_undo_history()
                    history.append(removed_item)
                    save_undo_history(history)

                save_category_data(category, new_unreviewed, new_reviewed)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/undo":
            history = load_undo_history()
            if not history:
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "empty", "message": "تاریخچه‌ای برای بازگرداندن وجود ندارد."}, ensure_ascii=False).encode("utf-8"))
                return

            last_action = history.pop()
            save_undo_history(history)

            item = last_action["item"]
            list_type = last_action["list_type"]
            cat = last_action["category"]
            clean_url = normalize_url(item["url"])

            blacklist = load_blacklist()
            if clean_url in blacklist:
                blacklist.remove(clean_url)
                save_blacklist(blacklist)

            unreviewed, reviewed = load_category_data(cat)
            if list_type == "unreviewed":
                unreviewed.append(item)
            else:
                reviewed.append(item)
            save_category_data(cat, unreviewed, reviewed)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "restored": item}, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/move-to-reviewed":
            category = query_params.get("category", [""])[0].strip().lower()
            if category:
                unreviewed, reviewed = load_category_data(category)
                reviewed.extend(unreviewed)
                unreviewed = []
                save_category_data(category, unreviewed, reviewed)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}, ensure_ascii=False).encode("utf-8"))
            return
        if path == "/update-post-date":
                    category = query_params.get("category", [""])[0].strip().lower()
                    url_to_update = query_params.get("url", [""])[0]
                    if category and url_to_update:
                        clean_url = normalize_url(url_to_update)
                        unreviewed, reviewed = load_category_data(category)
                        updated = False
                        for item in reviewed:
                            if normalize_url(item["url"]) == clean_url:
                                # ثبت تاریخ و ساعت فعلی
                                item["last_posted"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                                updated = True
                        if updated:
                            save_category_data(category, unreviewed, reviewed)
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "success"}, ensure_ascii=False).encode("utf-8"))
                    return
        if path == "/move-group-to-category":
            url_to_move = query_params.get("url", [""])[0]
            from_cat = query_params.get("from_category", [""])[0].strip().lower()
            to_cat = query_params.get("to_category", [""])[0].strip().lower()
            
            if url_to_move and from_cat and to_cat and from_cat != to_cat:
                clean_url = normalize_url(url_to_move)
                
                # خواندن داده‌های دسته مبدأ
                unrev_from, rev_from = load_category_data(from_cat)
                moved_item = None
                
                new_unrev_from = []
                for item in unrev_from:
                    if normalize_url(item["url"]) == clean_url:
                        moved_item = item
                    else:
                        new_unrev_from.append(item)
                        
                new_rev_from = []
                for item in rev_from:
                    if normalize_url(item["url"]) == clean_url:
                        moved_item = item
                    else:
                        new_rev_from.append(item)
                
                if moved_item:
                    # آپدیت دسته‌بندی در خود آیتم
                    moved_item["category"] = to_cat
                    # ذخیره تغییرات دسته مبدأ
                    save_category_data(from_cat, new_unrev_from, new_rev_from)
                    
                    # خواندن داده‌های دسته مقصد و اضافه کردن به بخش بررسی‌شده‌ی آن
                    unrev_to, rev_to = load_category_data(to_cat)
                    # چک کنیم تکراری نباشد
                    existing_to_urls = {normalize_url(i["url"]) for i in unrev_to + rev_to}
                    if clean_url not in existing_to_urls:
                        rev_to.append(moved_item)
                        save_category_data(to_cat, unrev_to, rev_to)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/add-manual-group":
            category = query_params.get("category", [""])[0].strip().lower()
            url_val = query_params.get("url", [""])[0]
            name_val = query_params.get("name", [""])[0]
            desc_val = query_params.get("description", [""])[0]

            if category and url_val:
                clean_url = normalize_url(url_val)
                unreviewed, reviewed = load_category_data(category)
                
                # بررسی اینکه آیا لینک قبلاً در لیست‌ها وجود دارد یا خیر
                existing_urls = {normalize_url(item["url"]) for item in unreviewed + reviewed}
                
                if clean_url not in existing_urls:
                    new_item = {
                        "url": clean_url,
                        "slug": extract_group_slug(clean_url),
                        "name": name_val,
                        "description": desc_val,
                        "category": category,
                        "analyzed_at": datetime.utcnow().isoformat()
                    }
                    reviewed.append(new_item)
                    save_category_data(category, unreviewed, reviewed)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}, ensure_ascii=False).encode("utf-8"))
            return
        try:
            with open("index.html", "r", encoding="utf-8") as f:
                html_template = f.read()
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Error: index.html not found!")
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html_template.encode("utf-8"))

def run():
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, WebHandler)
    print(f"Server running on port {PORT} with Data directory structured cleanly...")
    httpd.serve_forever()

if __name__ == "__main__":
    run()