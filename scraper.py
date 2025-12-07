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
# 请确保此路径指向您本地正确的 chromedriver 文件
CHROME_DRIVER_PATH = '/Users/yuliu/PycharmProjects/NYTimes/chromedriver'


def get_driver():
    """
    Initializes and returns a Selenium WebDriver instance.
    """
    chrome_options = Options()
    # 调试时如果想看浏览器运行，可以注释掉下面这行 '--headless'
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
        print(f"Please check if '{CHROME_DRIVER_PATH}' exists and matches your Chrome version.")
        return None


def scrape_nytimes():
    output_dir = 'articles'
    os.makedirs(output_dir, exist_ok=True)

    base_url = "https://cn.nytimes.com"
    homepage_url = f"{base_url}/zh-hant/"

    today_str = datetime.date.today().strftime("%A, %B %d, %Y")

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
        <title>纽约时报双语版 - The New York Times Bilingual Reader</title>
        <style>
            :root {{
                --nyt-black: #121212;
                --nyt-gray: #727272;
                --nyt-border: #e2e2e2;
                --bg-color: #f8f9fa;
            }}
            body {{
                font-family: 'Georgia', 'Times New Roman', serif;
                background-color: var(--bg-color);
                color: var(--nyt-black);
                margin: 0;
                padding: 0;
                line-height: 1.5;
            }}
            .app-container {{
                max-width: 800px;
                margin: 0 auto;
                background: #fff;
                min-height: 100vh;
                box-shadow: 0 0 20px rgba(0,0,0,0.05);
                padding-bottom: 40px;
            }}
            header {{
                padding: 40px 20px 20px 20px;
                text-align: center;
                margin-bottom: 20px;
            }}
            .masthead {{
                font-family: 'Chomsky', 'Georgia', 'Times New Roman', serif;
                font-size: 3.5rem;
                margin: 0;
                font-weight: 900;
                letter-spacing: -1px;
                line-height: 1;
                color: #000;
                margin-bottom: 10px;
            }}
            .sub-masthead {{
                font-family: system-ui, -apple-system, sans-serif;
                font-size: 1.2rem;
                font-weight: 700;
                color: #333;
                margin-bottom: 15px;
                letter-spacing: 1px;
            }}
            .date-line {{
                border-top: 1px solid #ddd;
                border-bottom: 3px double #000;
                padding: 8px 0;
                font-family: sans-serif;
                font-size: 0.85rem;
                color: #555;
                display: flex;
                justify-content: space-between;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            ul {{
                list-style: none;
                padding: 0 30px;
                margin: 0;
            }}
            li {{
                padding: 25px 0;
                border-bottom: 1px solid var(--nyt-border);
                transition: background-color 0.2s;
            }}
            li:last-child {{
                border-bottom: none;
            }}
            li:hover .article-title {{
                color: #00589c;
            }}
            a {{
                text-decoration: none;
                color: inherit;
                display: block;
            }}
            .article-title {{
                font-size: 1.4rem;
                font-weight: 700;
                margin-bottom: 8px;
                line-height: 1.3;
                color: #000;
                transition: color 0.2s;
            }}
            .article-meta {{
                font-family: sans-serif;
                font-size: 0.8rem;
                color: var(--nyt-gray);
                display: flex;
                align-items: center;
            }}
            .tag {{
                text-transform: uppercase;
                font-weight: 700;
                font-size: 0.7rem;
                margin-right: 10px;
                color: #000;
            }}
            @media (max-width: 600px) {{
                .masthead {{ font-size: 2.5rem; }}
                .date-line {{ flex-direction: column; align-items: center; gap: 5px; }}
            }}
        </style>
    </head>
    <body>
        <div class="app-container">
            <header>
                <div class="masthead">The New York Times</div>
                <div class="sub-masthead">纽约时报双语版</div>
                <div class="date-line">
                    <span>{today_str}</span>
                    <span>Bilingual Selection</span>
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
        # 清理标题中的换行和多余空格
        raw_title = link.text.strip().replace('\n', ' ')

        if not (href and raw_title and article_pattern.search(href)):
            continue
        if href in unique_links:
            continue
        if 'cn.nytimes.com' in href and not href.startswith('http'):
            continue

        unique_links[href] = raw_title
        absolute_url = urljoin(base_url, href)

        # --- 准备路径和日期 ---
        clean_url = absolute_url.split('?')[0].rstrip('/')
        if clean_url.endswith('/zh-hant'):
            clean_url = clean_url[:-len('/zh-hant')]

        # 从 URL 提取日期
        date_match = re.search(r'/(\d{4})(\d{2})(\d{2})/', clean_url)
        date_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}" if date_match else "Recent"

        slug = clean_url.split('/')[-1]
        local_filename = f"{slug}.html"
        local_filepath = os.path.join(output_dir, local_filename)

        final_page_title = raw_title  # 默认使用首页链接文字

        # --- 1. 检查文件是否已存在 ---
        if os.path.exists(local_filepath):
            print(f"\n[SKIP] File exists: {local_filename}")
            # 尝试从本地文件中读取精准标题
            try:
                with open(local_filepath, 'r', encoding='utf-8') as f:
                    # 只读取前 2048 字节通常足够获取 title，提高速度
                    existing_head = f.read(4096)
                    head_soup = BeautifulSoup(existing_head, 'html.parser')
                    if head_soup.title:
                        # 移除 "- NYTimes" 后缀以保持列表整洁
                        final_page_title = head_soup.title.text.replace(" - NYTimes", "").strip()
            except Exception as e:
                print(f"  -> Warning: Could not read title from local file: {e}")

            # 直接添加到列表，不下载
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
                page_title_tag = article_soup.find('h1')
                if page_title_tag:
                    final_page_title = page_title_tag.text.strip().replace('\n', ' ')

                # HTML 转义标题，防止引号破坏标签
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

    # 生成 index.html
    full_index_html = index_html_head + "\n".join(list_items) + """
            </ul>
            <footer style="text-align: center; padding: 40px 20px; color: #999; font-size: 0.8rem; font-family: sans-serif; border-top: 1px solid #eee; margin-top: 40px;">
                <p>Generated locally for personal study.</p>
            </footer>
        </div>
    </body>
    </html>
    """

    # 始终重新生成 index.html，以确保包含最新的已有文件列表
    if processed_articles > 0 or len(list_items) > 0:
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(full_index_html)
        print(
            f"\nDone! Processed {processed_articles} new articles (Total in index: {len(list_items)}). Open 'index.html' to view.")
    else:
        print("\nNo articles found.")


if __name__ == "__main__":
    scrape_nytimes()