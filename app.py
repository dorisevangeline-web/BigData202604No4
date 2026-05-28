from flask import Flask, render_template, jsonify
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
from urllib.parse import urljoin
import re
import os

app = Flask(__name__)

TARGET_STORES = [
    {"name": "全家", "url": "https://www.family.com.tw/Marketing/zh"},
    {"name": "7-11", "url": "https://www.citycafe.com.tw/"},
    {"name": "萊爾富", "url": "https://www.hilife.com.tw/events_activity.aspx"}
]

TARGET_KEYWORDS = ["折", "搭配", "特價", "加價"]
FILTER_KEYWORDS = ["icon", "logo", "arrow", "btn", "button", "footer", "header", "svg", "line", "facebook", "instagram", "app", "download"]

def fetch_all_events():
    events_data = []
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("window-size=1920,1080")
    
    # 反爬蟲破解參數
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = None
    try:
        print("\n🚀 啟動三大超商優惠掃描機器人 (含全家專屬優化版)...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
          "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
        
        for store in TARGET_STORES:
            store_name = store["name"]
            base_url = store["url"]
            
            print(f"\n🌍 正在前往 {store_name} 官網...")
            driver.get(base_url)
            
            # 🌟 針對不同超商，採用不同的等待與滾動策略
            if store_name == "全家":
                try:
                    print("⏳ [全家] 智慧等待主要內容載入中...")
                    # 智慧等待：最多等 10 秒，直到網頁中出現 img 標籤為止
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "img")))
                except:
                    print("⚠️ [全家] 載入超時，強制繼續執行")
                
                # 全家網頁通常較長，稍微多滾動幾次確保圖片懶載入觸發
                for _ in range(3):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1)
            else:
                # 7-11 與萊爾富維持原本的滾動方式
                time.sleep(3) 
                for _ in range(4):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1.5)
                    
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1.5)
            
            soup = BeautifulSoup(driver.page_source, "html.parser")
            
            # 🌟 針對全家優化：剔除 Header 與 Footer，只保留主要內容區塊
            if store_name == "全家":
                # 嘗試尋找主要內容區塊，若找不到才退回使用整個網頁
                main_content = soup.find("main") or soup.find("div", id="app") or soup
                # 移除 header 與 footer 標籤以減少雜訊
                for unwanted in main_content.find_all(['header', 'footer', 'nav']):
                    unwanted.decompose()
                all_links = main_content.find_all("a")
            else:
                all_links = soup.find_all("a")
                
            print(f"🔍 {store_name} 掃描到 {len(all_links)} 個有效區塊，開始過濾...")

            for link_tag in all_links:
                link = link_tag.get("href", "").strip()
                
                if not link or link == "#" or link.lower().startswith("javascript"):
                    absolute_link = base_url
                else:
                    absolute_link = urljoin(base_url, link)

                full_text = link_tag.get_text(strip=True)
                img_tag = link_tag.find("img")
                alt_text = img_tag.get("alt", "") if img_tag else ""
                title_text = link_tag.get("title", "")
                
                img_url = ""
                if img_tag:
                    img_url = img_tag.get("data-src") or img_tag.get("data-original") or img_tag.get("src") or ""
                
                if not img_url:
                    style_attr = link_tag.get("style", "")
                    if img_tag: 
                        style_attr += img_tag.get("style", "")
                    bg_match = re.search(r'url\([\'"]?(.*?)[\'"]?\)', style_attr)
                    if bg_match:
                        img_url = bg_match.group(1)

                if not img_url:
                    continue 

                if not img_url.startswith("data:image"):
                    img_url = urljoin(base_url, img_url)

                if any(word in img_url.lower() for word in FILTER_KEYWORDS):
                    continue

                combined_text = (full_text + alt_text + title_text).lower()
                url_text = (link + img_url).lower()
                
                is_target_event = False
                
                # 條件 A：純文字包含咖啡/飲品
                if any(key.lower() in combined_text for key in TARGET_KEYWORDS):
                    is_target_event = True
                
                # 條件 B：圖片檔名或連結包含活動關鍵字
                elif any(key in url_text for key in ["coffee", "cafe", "tea", "drink", "promo", "event", "banner", "campaign"]):
                    is_target_event = True
                    
                # 🌟 條件 C (全家專屬)：如果網址明確指向全家的活動頁面，提高收錄機率
                elif store_name == "全家" and ("/Campaign/" in link or "Event" in link):
                    is_target_event = True

                elif store_name in ["7-11", "萊爾富"] and ("banner" in img_url.lower() or "event" in img_url.lower()):
                    is_target_event = True

                if is_target_event:
                    event_title = alt_text or title_text or full_text or f"{store_name} 最新活動"
                    
                    event = {
                        "store": store_name,
                        "title": event_title.strip()[:40],
                        "img_url": img_url,
                        "link": absolute_link
                    }
                    
                    if event not in events_data:
                        events_data.append(event)
                            
            print(f"✅ {store_name} 過濾完畢！")
                            
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")
    finally:
        if driver:
            driver.quit() 
            
    return events_data

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/update')
def update_events():
    data = fetch_all_events()
    return jsonify(data)

if __name__ == '__main__':
    # 讓 Render 動態決定 Port，如果讀不到（例如你在本機測試），就預設用 8080
    port = int(os.environ.get('PORT', 8080))
    
    # host='0.0.0.0' 是對外公開的關鍵；debug=True 也可以繼續保留
    app.run(host='0.0.0.0', port=port, debug=True)
