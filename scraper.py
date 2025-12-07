import time
import re
import os
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
    # 如果调试时想看到浏览器运行，可以注释掉下面这行 '--headless'
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

    driver = get_driver()
    if not driver:
        return

    try:
        print(f"Fetching homepage: {homepage_url}")
        driver.get(homepage_url)
        time.sleep(5)  # 等待页面完全加载
        homepage_html = driver.page_source
    except Exception as e:
        print(f"Failed to load homepage: {e}")
        driver.quit()
        return

    soup = BeautifulSoup(homepage_html, 'html.parser')
    all_links = soup.find_all('a')

    # 初始化索引页 HTML
    index_html_content = """
    <!DOCTYPE html><html lang="zh-Hant"><head><meta charset="UTF-8"><title>纽约时报双语文章 (本地保存版)</title>
    <style>
        body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;line-height:1.6;margin:2em auto;max-width:800px;padding:0 1em;color:#333}
        h1{color:#000;border-bottom:2px solid #eee;padding-bottom:.5em}
        ul{list-style-type:decimal;padding-left:2em}
        li{margin-bottom:1em}
        a{text-decoration:none;color:#00589c;font-weight:bold}
        a:hover{text-decoration:underline;color:#003d6b}
        .timestamp {font-size: 0.8em; color: #666; margin-left: 10px;}
    </style>
    </head><body><h1>纽约时报双语文章 (本地保存版)</h1><ul>
    """

    unique_links = {}
    # 匹配 /YYYYMMDD/ 格式的 URL
    article_pattern = re.compile(r'/\d{8}/')
    processed_articles = 0

    print(f"Found {len(all_links)} links on homepage. Filtering...")

    for link in all_links:
        href = link.get('href', '')
        title = link.text.strip()

        # 1. 基础过滤：必须有 href，有标题，且包含日期结构
        if not (href and title and article_pattern.search(href)):
            continue

        # 2. 去重
        if href in unique_links:
            continue

        # 3. 排除非 http 开头的完整域名干扰链接（虽然一般 href 是相对路径）
        if 'cn.nytimes.com' in href and not href.startswith('http'):
            continue

        absolute_url = urljoin(base_url, href)

        # 4. [已修复] 之前这里有一个过滤 2025 年的逻辑，导致当前文章被跳过。已删除。

        unique_links[href] = title
        print(f"\nProcessing: {title}")

        # --- 构造双语 URL ---
        # 逻辑：移除 URL 末尾可能存在的查询参数和 '/zh-hant'，强行加上 '/zh-hant/dual/'
        clean_url = absolute_url.split('?')[0].rstrip('/')
        if clean_url.endswith('/zh-hant'):
            clean_url = clean_url[:-len('/zh-hant')]

        bilingual_url = f"{clean_url}/zh-hant/dual/"
        print(f"  -> Target URL: {bilingual_url}")

        try:
            # 使用 Selenium 获取正文，比 requests 更稳定
            driver.get(bilingual_url)
            time.sleep(3)  # 给页面一点加载和 JS 执行的时间

            # 检查是否真的加载成功（简单的 404 检测）
            if "Page Not Found" in driver.title or "404" in driver.title:
                print("  -> Page not found or not available in dual mode. Skipping.")
                continue

            article_soup = BeautifulSoup(driver.page_source, 'html.parser')

            # 尝试定位文章主体，NYTimes 结构可能会变，这里多几个备选
            article_body = article_soup.find('div', class_='article-body') or \
                           article_soup.find('section', attrs={'name': 'articleBody'}) or \
                           article_soup.find('article') or \
                           article_soup.find('main')

            if article_body:
                # 获取标题
                page_title_tag = article_soup.find('h1')
                page_title = page_title_tag.text.strip() if page_title_tag else title

                # 生成本地 HTML
                # 我们保留页面中的样式，或者注入简单的样式来区分中英文
                local_filename = f"{clean_url.split('/')[-1]}.html"
                local_filepath = os.path.join(output_dir, local_filename)

                article_html = f'''
                <!DOCTYPE html><html lang="zh-Hant"><head><meta charset="UTF-8"><title>{page_title}</title>
                <style>
                    body {{ font-family: Georgia, serif; line-height: 1.8; margin: 2em auto; max-width: 800px; padding: 0 1em; background: #f9f9f9; }}
                    h1 {{ text-align: center; border-bottom: 1px solid #ccc; padding-bottom: 0.5em; margin-bottom: 1.5em; color: #000; }}
                    /* NYTimes Dual Mode Styles Simulation */
                    .article-paragraph {{ margin-bottom: 1.5em; }}
                    /* 简单的样式假设，实际结构可能需要根据抓取到的 HTML 微调 */
                    p {{ margin-bottom: 1.2em; }}
                    img {{ max-width: 100%; height: auto; display: block; margin: 1em auto; }}
                    figcaption {{ font-size: 0.9em; color: #666; text-align: center; }}
                </style>
                </head><body>
                <h1>{page_title}</h1>
                <div class="content">
                    {str(article_body)}
                </div>
                </body></html>'''

                with open(local_filepath, 'w', encoding='utf-8') as f:
                    f.write(article_html)

                print(f"  -> Saved: {local_filename}")
                index_html_content += f'<li><a href="{local_filepath}" target="_blank">{page_title}</a> <span class="timestamp">({bilingual_url})</span></li>\n'
                processed_articles += 1
            else:
                print(f"  -> Could not locate article body content.")

        except Exception as e:
            print(f"  -> Error fetching article: {e}")

    # 收尾
    driver.quit()

    index_html_content += "</ul></body></html>"

    if processed_articles > 0:
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(index_html_content)
        print(f"\nDone! Processed {processed_articles} articles. Open 'index.html' to view.")
    else:
        print("\nNo articles were processed.")


if __name__ == "__main__":
    scrape_nytimes()