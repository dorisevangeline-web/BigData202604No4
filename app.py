from flask import Flask, render_template, jsonify, request
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from webdriver_manager.chrome import ChromeDriverManager

from urllib.parse import urljoin

import time
import re
import os

app = Flask(__name__)

# ==========================================
# 超商網站
# ==========================================
TARGET_STORES = [
    {
        "name": "全家",
        "url": "https://www.family.com.tw/Marketing/zh/Event"
    },
    {
        "name": "7-11",
        "url": "https://www.7-11.com.tw/special/newsList.aspx"
    },
    {
        "name": "萊爾富",
        #"url": "https://www.hilife.com.tw/index.aspx"
        "url": "https://www.hilife.com.tw/events_activity.aspx"
    }
]

# ==========================================
# 活動關鍵字
# ==========================================
TARGET_KEYWORDS = [  
    "咖啡",
    "飲料",
    "冰品",
    "啤酒",
    "拿鐵",
    "美式",
    "霜淇淋",
    "第二杯",
    "優惠",
    "買一送一",
    "活動",

]

# ==========================================
# 過濾垃圾圖片
# ==========================================
FILTER_KEYWORDS = [
    "icon",
    "logo",
    "arrow",
    "btn",
    "button",
    "footer",
    "header",
    "svg",
    "facebook",
    "instagram",
    "line",
    "app",
    "download"
    "協會"
]


# ==========================================
# 建立 Chrome Driver
# ==========================================
def create_driver():
    chrome_options = Options()

    # 背景執行
    chrome_options.add_argument("--headless")

    # Linux / Render 必備
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("window-size=1920,1080")

    # 反爬蟲
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # 隱藏 webdriver
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined})
            """
        }
    )
    return driver


# ==========================================
# 全家專用爬蟲
# ==========================================
def fetch_family_events(driver, base_url):
    events = []
    print("\n🌍 前往全家網站...")
    driver.get(base_url)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "img"))
        )
    except:
        print("⚠️ 全家載入超時")

    # 慢速滾動
    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(6):
        driver.execute_script("window.scrollBy(0, 1200);")
        time.sleep(1.5)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    # 回到頂部
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(2)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    main_content = soup.find("main") or soup.find("div", id="app") or soup

    # 移除干擾元素
    for unwanted in main_content.find_all(["header", "footer", "nav", "script", "style"]):
        unwanted.decompose()

    # 強化活動抓取
    all_blocks = main_content.select(".event, .box, .card, .swiper-slide, li, .item, a")
    print(f"🔍 全家掃描到 {len(all_blocks)} 個區塊")

    seen_images = set()

    for block in all_blocks:
        try:
            link_tag = block.find("a") or block
            link = link_tag.get("href", "").strip()

            if not link or link.startswith("javascript"):
                absolute_link = base_url
            else:
                absolute_link = urljoin(base_url, link)

            full_text = block.get_text(strip=True)
            img_tag = block.find("img")
            alt_text = ""
            title_text = ""

            if img_tag:
                alt_text = img_tag.get("alt", "")

            title_text = block.get("title", "")

            # ==========================
            # 抓圖片
            # ==========================
            img_url = ""
            if img_tag:
                img_url = (
                    img_tag.get("data-src")
                    or img_tag.get("data-original")
                    or img_tag.get("srcset")
                    or img_tag.get("src")
                    or ""
                )
                # srcset 處理
                if "," in img_url:
                    img_url = img_url.split(",")[0].split(" ")[0]

            # background-image
            if not img_url:
                style_attr = block.get("style", "")
                if img_tag:
                    style_attr += img_tag.get("style", "")

                bg_match = re.search(r'url\([\'"]?(.*?)[\'"]?\)', style_attr)
                if bg_match:
                    img_url = bg_match.group(1)

            if not img_url:
                continue

            # 修正網址
            if img_url.startswith("//"):
                img_url = "https:" + img_url

            if not img_url.startswith("http"):
                img_url = urljoin(base_url, img_url)

            # 過濾垃圾圖
            if any(word in img_url.lower() for word in FILTER_KEYWORDS):
                continue

            # 避免重複
            if img_url in seen_images:
                continue
            seen_images.add(img_url)

            combined_text = (full_text + alt_text + title_text).lower()
            url_text = (link + img_url).lower()

            is_target_event = False

            # 關鍵字
            if any(key.lower() in combined_text for key in TARGET_KEYWORDS):
                is_target_event = True

            # URL 判斷
            elif any(key in url_text for key in ["coffee", "drink", "cafe", "event", "campaign", "promo", "banner"]):
                is_target_event = True

            # 全家活動頁專屬
            elif (
                "/Campaign/" in link
                or "/campaign/" in link.lower()
                or "/Marketing/" in link
                or "event" in link.lower()
                or "promo" in link.lower()
            ):
                is_target_event = True

            if is_target_event:
                event_title = alt_text or title_text or full_text or "全家最新活動"
                event_title = event_title.strip()

                # 避免垃圾文字
                if len(event_title) < 3:
                    continue

                event = {
                    "store": "全家",
                    "title": event_title[:40],
                    "img_url": img_url,
                    "link": absolute_link
                }
                events.append(event)

        except Exception as e:
            print(f"⚠️ 全家單筆錯誤: {e}")

    print(f"✅ 全家抓到 {len(events)} 筆活動")
    return events


# ==========================================
# 萊爾富專用爬蟲
# ==========================================
def fetch_hilife_events(driver, base_url):
    events = []
    print("\n🌍 前往萊爾富網站...")
    driver.get(base_url)

    # 等待頁面
    time.sleep(5)

    # 滾動頁面
    for _ in range(5):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)

    # 回到頂部
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    # ⭐ 直接抓 img
    all_images = soup.find_all("img")
    print(f"🔍 萊爾富找到 {len(all_images)} 張圖片")

    seen_images = set()

    for img in all_images:
        try:
            # ==========================
            # 圖片網址
            # ==========================
            img_url = img.get("data-src") or img.get("src") or ""
            if not img_url:
                continue

            # 修正網址
            if img_url.startswith("//"):
                img_url = "https:" + img_url

            img_url = urljoin(base_url, img_url)

            # ==========================
            # 過濾垃圾圖片
            # ==========================
            if any(word in img_url.lower() for word in FILTER_KEYWORDS):
                continue

            # 避免重複
            if img_url in seen_images:
                continue
            seen_images.add(img_url)

            # ==========================
            # 取得文字
            # ==========================
            alt_text = img.get("alt", "").strip()
            title_text = img.get("title", "").strip()

            # ==========================
            # 從父層找文字
            # ==========================
            parent_text = ""
            parent = img.parent
            for _ in range(3):
                if parent:
                    text = parent.get_text(" ", strip=True)
                    # 保留最長文字
                    if len(text) > len(parent_text):
                        parent_text = text
                    parent = parent.parent

            # ==========================
            # 合併所有文字
            # ==========================
            all_text = (alt_text + " " + title_text + " " + parent_text).strip()

            # ==========================
            # 修正原本程式未定義 href 與 event_link 的錯誤
            # ==========================
            parent_a = img.find_parent("a")
            href = parent_a.get("href", "").strip() if parent_a else ""
            event_link = urljoin(base_url, href) if href else base_url

            # ==========================
            # 活動判斷
            # ==========================
            combined_text = all_text.lower()
            url_text = (img_url + href).lower()
            is_target_event = False

            # 關鍵字判斷
            if any(key.lower() in combined_text for key in TARGET_KEYWORDS):
                is_target_event = True

            # URL 判斷
            elif any(key in url_text for key in ["event", "activity", "campaign", "banner", "coffee", "drink", "promo"]):
                is_target_event = True

            # 圖片尺寸過濾
            width = img.get("width", "")
            if width.isdigit() and int(width) < 100:
                continue

            # 非活動
            if not is_target_event:
                continue

            # ==========================
            # 活動標題
            # ==========================
            event_title = alt_text or title_text or parent_text or "萊爾富最新活動"
            event_title = event_title.strip()
            # 移除多餘空白 
            event_title = re.sub(r'\s+', ' ', event_title) 
            # 避免文字過長 
            event_title = event_title[:60]

            if len(event_title) < 2:
                event_title = "萊爾富最新活動"

            # ==========================
            # 建立資料
            # ==========================
            event = {
                "store": "萊爾富",
                "title": event_title[:40],
                "img_url": img_url,
                "link": event_link
            }
            events.append(event)

        except Exception as e:
            print(f"⚠️ 萊爾富單筆錯誤: {e}")

    print(f"✅ 萊爾富抓到 {len(events)} 筆活動")
    return events


# ==========================================
# 一般超商爬蟲（7-11）
# ==========================================
def fetch_normal_store(driver, store_name, base_url):
    events = []
    print(f"\n🌍 前往 {store_name} 網站...")
    driver.get(base_url)
    time.sleep(3)

    # 滾動頁面
    for _ in range(4):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)

    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    all_links = soup.find_all("a")
    print(f"🔍 {store_name} 掃描到 {len(all_links)} 個區塊")

    seen_images = set()

    for link_tag in all_links:
        try:
            link = link_tag.get("href", "").strip()
            if not link or link == "#":
                absolute_link = base_url
            else:
                absolute_link = urljoin(base_url, link)

            full_text = link_tag.get_text(strip=True)
            img_tag = link_tag.find("img")
            if not img_tag:
                continue

            alt_text = img_tag.get("alt", "")
            title_text = link_tag.get("title", "")

            img_url = img_tag.get("data-src") or img_tag.get("src") or ""
            if not img_url:
                continue

            if not img_url.startswith("http"):
                img_url = urljoin(base_url, img_url)

            # 過濾垃圾圖
            if any(word in img_url.lower() for word in FILTER_KEYWORDS):
                continue

            # 避免重複
            if img_url in seen_images:
                continue
            seen_images.add(img_url)

            combined_text = (full_text + alt_text + title_text).lower()
            is_target_event = False

            # 關鍵字
            if any(key.lower() in combined_text for key in TARGET_KEYWORDS):
                is_target_event = True

            # URL 判斷
            elif "banner" in img_url.lower() or "event" in img_url.lower():
                is_target_event = True

            if is_target_event:
                event_title = alt_text or title_text or full_text or f"{store_name} 最新活動"
                event_title = event_title.strip()

                if len(event_title) < 3:
                    continue

                event = {
                    "store": store_name,
                    "title": event_title[:40],
                    "img_url": img_url,
                    "link": absolute_link
                }
                events.append(event)

        except Exception as e:
            print(f"⚠️ {store_name} 單筆錯誤: {e}")

    print(f"✅ {store_name} 抓到 {len(events)} 筆活動")
    return events


# ==========================================
# 總抓取 (已修改：支援特定超商篩選)
# ==========================================
def fetch_all_events(target_store_name=None):
    events_data = []
    driver = None

    try:
        print("\n🚀 啟動超商優惠爬蟲系統")
        driver = create_driver()

        for store in TARGET_STORES:
            store_name = store["name"]
            
            # 若前端指定了特定超商，且與目前迴圈不合，就跳過不爬取
            if target_store_name and store_name != target_store_name:
                continue

            base_url = store["url"]

            # 全家
            if store_name == "全家":
                family_events = fetch_family_events(driver, base_url)
                events_data.extend(family_events)

            # 萊爾富
            elif store_name == "萊爾富":
                hilife_events = fetch_hilife_events(driver, base_url)
                events_data.extend(hilife_events)

            # 7-11
            else:
                normal_events = fetch_normal_store(driver, store_name, base_url)
                events_data.extend(normal_events)

    except Exception as e:
        print(f"❌ 系統錯誤: {e}")
    finally:
        if driver:
            driver.quit()

    return events_data


# ==========================================
# 首頁
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')


# ==========================================
# API 更新 (已修改：接收 store 參數)
# ==========================================
@app.route('/api/update')
def update_events():
    # 獲取前端網址傳來的 ?store=... 參數
    target_store = request.args.get('store')
    
    # 傳入篩選參數進行爬取
    data = fetch_all_events(target_store)

    return jsonify(data)


# ==========================================
# Flask 啟動
# ==========================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)