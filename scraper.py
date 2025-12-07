import time
import re
import os
import datetime
import html
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from urllib.parse import urljoin

# --- CONFIGURATION ---
CHROME_DRIVER_PATH = '/Users/yuliu/PycharmProjects/NYTimes/chromedriver'

# [控制開關] True = 強制重新下載所有文章； False = 跳過已存在的文件 (推薦)
FORCE_UPDATE = False


def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    service = Service(CHROME_DRIVER_PATH)
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        print(f"Error initializing ChromeDriver: {e}")
        return None


def slug_to_title_fallback(url):
    """(備用) 從 URL 中提取英文 slug 並轉換為標題格式"""
    try:
        match = re.search(r'/\d{8}/([^/]+)', url)
        if match:
            return match.group(1).replace('-', ' ').title()
    except:
        pass
    return ""


def is_valid_content(soup_or_text):
    """檢查內容是否為有效的文章，排除 404 頁面"""
    text = str(soup_or_text)
    invalid_markers = [
        "對不起，您訪問的頁面未找到",
        "您访问的页面未找到",
        "Page Not Found",
        "The page you requested could not be found",
        "我們為您推薦的熱門文章"
    ]
    for marker in invalid_markers:
        if marker in text:
            return False
    return True


def scrape_nytimes():
    output_dir = 'articles'
    os.makedirs(output_dir, exist_ok=True)

    base_url = "https://cn.nytimes.com"
    homepage_url = f"{base_url}/zh-hant/"

    today_str = datetime.date.today().strftime("%Y-%m-%d")

    driver = get_driver()
    if not driver:
        return

    try:
        print(f"Fetching homepage: {homepage_url}")
        driver.get(homepage_url)
        time.sleep(5)
        homepage_html = driver.page_source
    except Exception as e:
        print(f"Failed to load homepage: {e}")
        driver.quit()
        return

    soup = BeautifulSoup(homepage_html, 'html.parser')
    all_links = soup.find_all('a')

    # --- 首頁 HTML 頭部 ---
    index_html_head = f"""
    <!DOCTYPE html>
    <html lang="zh-Hant">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>紐約時報雙語版 - NYTimes Bilingual</title>
        <style>
            :root {{ --nyt-black: #121212; --nyt-gray: #727272; --nyt-border: #e2e2e2; --bg-color: #f8f9fa; }}
            body {{ font-family: 'Georgia', 'Times New Roman', serif; background-color: var(--bg-color); color: var(--nyt-black); margin: 0; padding: 0; line-height: 1.5; }}
            .app-container {{ max-width: 800px; margin: 0 auto; background: #fff; min-height: 100vh; box-shadow: 0 0 20px rgba(0,0,0,0.05); padding-bottom: 40px; }}
            header {{ padding: 40px 20px 20px 20px; text-align: center; margin-bottom: 20px; border-bottom: 4px double #000; }}
            .masthead {{ font-family: 'Georgia', serif; font-size: 3rem; margin: 0; font-weight: 900; letter-spacing: -1px; line-height: 1; color: #000; margin-bottom: 10px; }}
            .sub-masthead {{ font-family: sans-serif; font-size: 1.1rem; font-weight: 700; color: #333; margin-bottom: 15px; letter-spacing: 1px; }}
            .date-line {{ border-top: 1px solid #ddd; padding: 8px 0; font-family: sans-serif; font-size: 0.85rem; color: #555; display: flex; justify-content: space-between; text-transform: uppercase; }}
            ul {{ list-style: none; padding: 0 30px; margin: 0; }}
            li {{ padding: 25px 0; border-bottom: 1px solid var(--nyt-border); }}
            li:last-child {{ border-bottom: none; }}
            a {{ text-decoration: none; color: inherit; display: block; }}
            .article-title-cn {{ font-size: 1.4rem; font-weight: 700; margin-bottom: 4px; line-height: 1.3; color: #000; }}
            .article-title-en {{ font-size: 1.15rem; font-weight: 400; margin-bottom: 8px; line-height: 1.4; color: #444; font-style: italic; font-family: 'Georgia', serif; }}
            a:hover .article-title-cn {{ color: #00589c; }}
            .article-meta {{ font-family: sans-serif; font-size: 0.8rem; color: var(--nyt-gray); display: flex; align-items: center; }}
            .tag {{ text-transform: uppercase; font-weight: 700; font-size: 0.7rem; margin-right: 10px; color: #000; background: #eee; padding: 2px 6px; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <div class="app-container">
            <header>
                <div class="masthead">The New York Times</div>
                <div class="sub-masthead">紐約時報雙語版</div>
                <div class="date-line">
                    <span>{datetime.date.today().strftime("%A, %B %d, %Y")}</span>
                    <span>Daily Selection</span>
                </div>
            </header>
            <ul>
    """

    list_items = []
    unique_links = {}
    article_pattern = re.compile(r'/\d{8}/')
    processed_articles = 0

    print(f"Found {len(all_links)} links on homepage. Filtering...")

    for link in all_links:
        href = link.get('href', '')
        cn_title = link.text.strip().replace('\n', ' ')

        # 基礎過濾
        if not (href and cn_title and article_pattern.search(href)):
            continue

        # 過濾 2023/2024 (以及更早的)
        if any(x in href for x in ['/2023', '/2024', '/2022']):
            continue

        if href in unique_links:
            continue
        if 'cn.nytimes.com' in href and not href.startswith('http'):
            continue

        unique_links[href] = cn_title
        absolute_url = urljoin(base_url, href)
        clean_url = absolute_url.split('?')[0].rstrip('/')
        if clean_url.endswith('/zh-hant'):
            clean_url = clean_url[:-len('/zh-hant')]

        # 從 URL 提取日期
        date_match = re.search(r'/(\d{4})(\d{2})(\d{2})/', clean_url)
        date_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}" if date_match else today_str

        slug = clean_url.split('/')[-1]
        local_filename = f"{slug}.html"
        local_filepath = os.path.join(output_dir, local_filename)

        final_cn_title = cn_title
        final_en_title = slug_to_title_fallback(clean_url)  # 默認值

        # --- 1. 檢查文件是否存在 ---
        if os.path.exists(local_filepath):
            if not FORCE_UPDATE:
                # 檢查文件是否是“壞文件”（404 頁面）
                try:
                    with open(local_filepath, 'r', encoding='utf-8') as f:
                        content = f.read()

                    if not is_valid_content(content):
                        print(f"\n[DELETE] Found invalid local file (404 page): {local_filename}")
                        os.remove(local_filepath)
                        # 刪除後不 continue，讓它進入下方的下載流程（或者您可以選擇直接 skip）
                        # 這裡我們選擇重新下載，試試看能不能獲取到正確的
                    else:
                        # 文件存在且有效，讀取信息並跳過下載
                        print(f"\n[SKIP] Valid file exists: {local_filename}")
                        saved_en = re.search(r'<h2 class="en-headline">(.*?)</h2>', content)
                        if saved_en:
                            final_en_title = saved_en.group(1).strip()

                        list_items.append(f'''
                        <li>
                            <a href="{os.path.join('articles', local_filename)}" target="_blank">
                                <div class="article-title-cn">{final_cn_title}</div>
                                <div class="article-title-en">{final_en_title}</div>
                                <div class="article-meta">
                                    <span class="tag">CACHED</span>
                                    <span class="date">{date_str}</span>
                                </div>
                            </a>
                        </li>
                        ''')
                        processed_articles += 1
                        continue
                except Exception as e:
                    print(f"Error reading local file: {e}")
            else:
                # 強制更新模式，忽略本地文件
                pass

        # --- 2. 下載文章 ---
        print(f"\n[DOWNLOADING] {cn_title}")
        bilingual_url = f"{clean_url}/zh-hant/dual/"

        try:
            driver.get(bilingual_url)
            time.sleep(3)

            # 檢查標題和內容是否包含 404 關鍵詞
            page_source = driver.page_source
            if "Page Not Found" in driver.title or "404" in driver.title or not is_valid_content(page_source):
                print("  -> Page content invalid (likely 404). Skipping.")
                continue

            article_soup = BeautifulSoup(page_source, 'html.parser')
            article_body = article_soup.find('div', class_='article-body') or \
                           article_soup.find('section', attrs={'name': 'articleBody'}) or \
                           article_soup.find('article') or \
                           article_soup.find('main')

            if article_body:
                # 二次檢查 body 內容是否有效
                if not is_valid_content(article_body):
                    print("  -> Article body contains error message. Skipping.")
                    continue

                # --- 提取英文標題 ---
                real_en_title = None

                # 策略 1: 查找特定 class
                header_tags = article_soup.find_all(['h1', 'span', 'div', 'h2'])
                for tag in header_tags:
                    # 檢查 class 是否包含 'en' 且是標題相關的
                    classes = tag.get('class', [])
                    if classes and any('en' in c for c in classes) and any(
                            k in str(classes).lower() for k in ['title', 'headline']):
                        if tag.text.strip():
                            real_en_title = tag.text.strip()
                            break

                # 策略 2: 查找緊跟在中文 H1 後面的英文內容
                if not real_en_title:
                    h1_cn = article_soup.find('h1')
                    if h1_cn:
                        span_en = h1_cn.find('span', class_='en')
                        if span_en:
                            real_en_title = span_en.text.strip()
                        elif h1_cn.find_next_sibling(['h1', 'h2', 'div', 'span']):
                            sib = h1_cn.find_next_sibling()
                            # 簡單的啟發式：如果兄弟節點包含大量英文字符
                            if sib and len(sib.text) > 5 and re.search(r'[a-zA-Z]', sib.text):
                                real_en_title = sib.text.strip()

                if real_en_title:
                    final_en_title = real_en_title
                    print(f"  -> Found English title: {final_en_title}")

                safe_cn_title = html.escape(final_cn_title)
                safe_en_title = html.escape(final_en_title)

                # 生成文章頁
                article_html = f'''
                <!DOCTYPE html>
                <html lang="zh-Hant">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>{safe_cn_title} - NYTimes</title>
                    <style>
                        body {{ font-family: 'Georgia', 'Times New Roman', serif; line-height: 1.8; margin: 0; padding: 0; background: #fdfdfd; color: #111; }}
                        .content-container {{ max-width: 700px; margin: 0 auto; background: #fff; padding: 40px 20px; min-height: 100vh; }}

                        h1.cn-headline {{ font-family: "Pieter", "Georgia", serif; font-weight: 700; margin-bottom: 10px; font-size: 2.2rem; line-height: 1.2; color: #000; }}
                        h2.en-headline {{ font-family: "Georgia", serif; font-weight: 400; font-style: italic; margin-top: 0; margin-bottom: 1.5em; font-size: 1.5rem; color: #555; }}

                        .meta {{ color: #666; font-family: sans-serif; font-size: 0.85rem; margin-bottom: 2.5em; border-top: 1px solid #ddd; padding-top: 1em; text-transform: uppercase; letter-spacing: 0.5px; }}

                        .article-paragraph {{ margin-bottom: 2em; }}
                        p {{ margin: 0 0 1em 0; }}
                        .en-p {{ color: #222; margin-bottom: 0.8em; font-size: 1.1rem; }}
                        .cn-p {{ color: #004276; font-weight: 500; font-size: 1.05rem; line-height: 1.8; }}

                        figure {{ margin: 2em 0; width: 100%; }}
                        img {{ max-width: 100%; height: auto; display: block; background: #f0f0f0; }}
                        figcaption {{ font-size: 0.85rem; color: #888; margin-top: 0.5em; font-family: sans-serif; text-align: center; }}

                        .back-link {{ display: inline-block; margin-bottom: 20px; color: #999; text-decoration: none; font-family: sans-serif; font-size: 0.8rem; }}
                        .back-link:hover {{ text-decoration: underline; color: #333; }}
                    </style>
                </head>
                <body>
                <div class="content-container">
                    <a href="../index.html" class="back-link">← Back to Index</a>

                    <h1 class="cn-headline">{final_cn_title}</h1>
                    <h2 class="en-headline">{final_en_title}</h2>

                    <div class="meta">{date_str} • The New York Times</div>

                    <div class="article-body">
                        {str(article_body)}
                    </div>
                </div>
                </body></html>'''

                with open(local_filepath, 'w', encoding='utf-8') as f:
                    f.write(article_html)

                print(f"  -> Saved: {local_filename}")

                list_items.append(f'''
                <li>
                    <a href="{os.path.join('articles', local_filename)}" target="_blank">
                        <div class="article-title-cn">{final_cn_title}</div>
                        <div class="article-title-en">{final_en_title}</div>
                        <div class="article-meta">
                            <span class="tag">NEW</span>
                            <span class="date">{date_str}</span>
                        </div>
                    </a>
                </li>
                ''')
                processed_articles += 1
            else:
                print(f"  -> Could not locate article body content.")

        except Exception as e:
            print(f"  -> Error fetching article: {e}")

    driver.quit()

    full_index_html = index_html_head + "\n".join(list_items) + """
            </ul>
            <footer style="text-align: center; padding: 40px 20px; color: #999; font-size: 0.8rem; font-family: sans-serif; border-top: 1px solid #eee; margin-top: 40px;">
                <p>Generated locally for personal study.</p>
            </footer>
        </div>
    </body>
    </html>
    """

    if len(list_items) > 0:
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(full_index_html)
        print(f"\nDone! Index updated with {len(list_items)} articles.")
    else:
        print("\nNo valid articles found.")


if __name__ == "__main__":
    scrape_nytimes()