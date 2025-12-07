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


def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")

    # 防止部分自动化检测
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

    # --- 首页 HTML 头部 ---
    index_html_head = f"""
    <!DOCTYPE html>
    <html lang="zh-Hant">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>纽约时报双语版 - NYTimes Bilingual</title>
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
            .article-title {{ font-size: 1.4rem; font-weight: 700; margin-bottom: 8px; line-height: 1.3; color: #000; }}
            a:hover .article-title {{ color: #00589c; }}
            .article-meta {{ font-family: sans-serif; font-size: 0.8rem; color: var(--nyt-gray); display: flex; align-items: center; }}
            .tag {{ text-transform: uppercase; font-weight: 700; font-size: 0.7rem; margin-right: 10px; color: #000; background: #eee; padding: 2px 6px; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <div class="app-container">
            <header>
                <div class="masthead">The New York Times</div>
                <div class="sub-masthead">纽约时报双语版</div>
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
        # 从首页链接获取最原始的标题（通常是最准确的）
        raw_title = link.text.strip().replace('\n', ' ')

        if not (href and raw_title and article_pattern.search(href)):
            continue
        if href in unique_links:
            continue
        if 'cn.nytimes.com' in href and not href.startswith('http'):
            continue

        unique_links[href] = raw_title
        absolute_url = urljoin(base_url, href)

        clean_url = absolute_url.split('?')[0].rstrip('/')
        if clean_url.endswith('/zh-hant'):
            clean_url = clean_url[:-len('/zh-hant')]

        # 从 URL 提取日期
        date_match = re.search(r'/(\d{4})(\d{2})(\d{2})/', clean_url)
        date_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}" if date_match else today_str

        slug = clean_url.split('/')[-1]
        local_filename = f"{slug}.html"
        local_filepath = os.path.join(output_dir, local_filename)

        final_page_title = raw_title  # 默认使用首页链接文字

        # --- 1. 检查文件是否已存在 (并修复标题) ---
        if os.path.exists(local_filepath):
            print(f"\n[CHECKING] File exists: {local_filename}")
            file_needs_update = False

            try:
                # 读取全部内容以进行解析和可能的替换
                with open(local_filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                head_soup = BeautifulSoup(content, 'html.parser')
                existing_title_tag = head_soup.title
                existing_title_text = existing_title_tag.text.strip() if existing_title_tag else ""

                # 检查条件：如果没有 title 标签，或者 title 为空，或者 title 仅仅是 "NYTimes" 这种无效标题
                if not existing_title_text or existing_title_text == "NYTimes" or existing_title_text == "The New York Times":
                    print(f"  -> Missing or bad title in file. Fixing with: {raw_title}")
                    final_page_title = raw_title

                    # 构造新的 title 标签
                    new_title_tag = f"<title>{html.escape(raw_title)} - NYTimes</title>"

                    if existing_title_tag:
                        # 替换旧标签
                        content = content.replace(str(existing_title_tag), new_title_tag)
                    else:
                        # 插入新标签到 head
                        content = content.replace("<head>", f"<head>{new_title_tag}")

                    file_needs_update = True
                else:
                    # 如果本地文件标题正常，就用本地文件的（去除后缀）
                    final_page_title = existing_title_text.replace(" - NYTimes", "").strip()

                if file_needs_update:
                    with open(local_filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print("  -> File updated with correct title.")

            except Exception as e:
                print(f"  -> Warning: Could not read/fix local file: {e}")

            # 添加到列表
            list_items.append(f'''
            <li>
                <a href="{os.path.join('articles', local_filename)}" target="_blank">
                    <div class="article-title">{final_page_title}</div>
                    <div class="article-meta">
                        <span class="tag">CACHED</span>
                        <span class="date">{date_str}</span>
                    </div>
                </a>
            </li>
            ''')
            processed_articles += 1
            continue

        # --- 2. 文件不存在，执行下载 ---
        print(f"\n[DOWNLOADING] {raw_title}")
        bilingual_url = f"{clean_url}/zh-hant/dual/"

        try:
            driver.get(bilingual_url)
            time.sleep(3)

            if "Page Not Found" in driver.title or "404" in driver.title:
                print("  -> Page not found. Skipping.")
                continue

            article_soup = BeautifulSoup(driver.page_source, 'html.parser')
            article_body = article_soup.find('div', class_='article-body') or \
                           article_soup.find('section', attrs={'name': 'articleBody'}) or \
                           article_soup.find('article') or \
                           article_soup.find('main')

            if article_body:
                # 尝试从文章页获取 H1，如果获取不到，回退使用首页链接的 raw_title
                page_h1 = article_soup.find('h1')
                if page_h1 and page_h1.text.strip():
                    final_page_title = page_h1.text.strip().replace('\n', ' ')
                else:
                    final_page_title = raw_title

                safe_title = html.escape(final_page_title)

                article_html = f'''
                <!DOCTYPE html>
                <html lang="zh-Hant">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>{safe_title} - NYTimes</title>
                    <style>
                        body {{ font-family: 'Georgia', 'Times New Roman', serif; line-height: 1.8; margin: 0; padding: 0; background: #fdfdfd; color: #111; }}
                        .content-container {{ max-width: 700px; margin: 0 auto; background: #fff; padding: 40px 20px; min-height: 100vh; }}
                        h1 {{ font-family: 'Georgia', serif; font-style: italic; margin-bottom: 0.5em; font-size: 2.2rem; line-height: 1.2; color: #000; }}
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
                    <h1>{final_page_title}</h1>
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
                        <div class="article-title">{final_page_title}</div>
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

    # 只要有处理过的文章或者列表不为空，就生成 index.html
    if len(list_items) > 0:
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(full_index_html)
        print(f"\nDone! Processed {len(list_items)} articles. Open 'index.html' to view.")
    else:
        print("\nNo articles found.")


if __name__ == "__main__":
    scrape_nytimes()