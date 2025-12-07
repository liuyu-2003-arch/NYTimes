import time
import re
import os
import datetime
import html
import json
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from urllib.parse import urljoin
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
TEMPLATE_FILE = 'article_template.html'
ARTICLES_PER_PAGE = 10  # 每页显示的文章数量

# 设为 True 运行一次以更新所有文章的顶部控制栏样式
FORCE_UPDATE = os.getenv('FORCE_UPDATE', 'False') == 'True'


def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        print(f"Error initializing ChromeDriver: {e}")
        return None


def load_template():
    if not os.path.exists(TEMPLATE_FILE):
        print(f"Error: Template file '{TEMPLATE_FILE}' not found!")
        return None
    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        return f.read()


def is_valid_content(soup_or_text):
    text = str(soup_or_text)
    invalid_markers = ["Page Not Found", "頁面未找到", "页面未找到"]
    for marker in invalid_markers:
        if marker in text: return False
    return True


def clean_text(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', text.strip())


def is_brand_name(text):
    if not text: return True
    lower = text.lower()
    brands = ["new york times", "nytimes", "紐約時報", "纽约时报", "chinese website", "中文网"]
    cleaned = re.sub(r'[^a-zA-Z\u4e00-\u9fff]', '', lower)
    for b in brands:
        if b.replace(" ", "") in cleaned and len(cleaned) < len(b.replace(" ", "")) + 5:
            return True
    return False


def extract_titles_from_page_title(browser_title):
    if not browser_title: return None, None
    parts = re.split(r'\s+[-–—]\s+', browser_title)
    cn = None
    en = None
    if len(parts) >= 1: cn = clean_text(parts[0])
    for part in parts[1:]:
        p = clean_text(part)
        if re.match(r'^[A-Za-z0-9\s:,\.\-\?\'"’]+$', p) and not is_brand_name(p):
            en = p
            break
    return cn, en


def extract_author(soup):
    try:
        scripts = soup.find_all('script', type='application/ld+json')
        for s in scripts:
            data = json.loads(s.string)
            if isinstance(data, list): data = data[0]
            if 'author' in data:
                authors = data['author']
                if isinstance(authors, list):
                    names = [a.get('name') for a in authors if a.get('name')]
                    return ", ".join(names)
                elif isinstance(authors, dict):
                    return authors.get('name', '')
            if 'creator' in data:
                return str(data['creator'])
    except:
        pass

    address = soup.find('address')
    if address: return clean_text(address.text)

    meta_byl = soup.find('meta', attrs={'name': 'byl'})
    if meta_byl: return clean_text(meta_byl.get('content'))

    return "The New York Times"


def scrape_nytimes():
    output_dir = 'articles'
    os.makedirs(output_dir, exist_ok=True)

    template_content = load_template()
    if not template_content: return

    base_url = "https://cn.nytimes.com"
    homepage_url = f"{base_url}/zh-hant/"
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    driver = get_driver()
    if not driver: return

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

    # 用于存储纯数据
    articles_data = []

    unique_links = {}
    article_pattern = re.compile(r'/\d{8}/')

    print(f"Found {len(all_links)} links on homepage. Filtering...")

    for link in all_links:
        href = link.get('href', '')
        homepage_title_hint = clean_text(link.text)

        if not (href and homepage_title_hint and article_pattern.search(href)): continue
        if any(x in href for x in ['/2023', '/2024', '/2022']): continue
        if href in unique_links: continue
        if 'cn.nytimes.com' in href and not href.startswith('http'): continue

        unique_links[href] = homepage_title_hint
        absolute_url = urljoin(base_url, href)
        clean_url = absolute_url.split('?')[0].rstrip('/')
        if clean_url.endswith('/zh-hant'): clean_url = clean_url[:-len('/zh-hant')]

        date_match = re.search(r'/(\d{4})(\d{2})(\d{2})/', clean_url)
        date_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}" if date_match else "Recent"

        slug = clean_url.split('/')[-1]
        local_filename = f"{slug}.html"
        local_filepath = os.path.join(output_dir, local_filename)

        final_cn_title = homepage_title_hint
        final_en_title = ""
        need_download = True
        status_tag = "NEW"

        # --- 1. Check Local File ---
        if os.path.exists(local_filepath) and not FORCE_UPDATE:
            try:
                with open(local_filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                if not is_valid_content(content):
                    print(f"\n[DELETE] Invalid content: {local_filename}")
                    os.remove(local_filepath)
                else:
                    saved_en_match = re.search(r'<h2 class="en-headline">(.*?)</h2>', content)
                    saved_en = saved_en_match.group(1).strip() if saved_en_match else ""
                    has_trash = "翻譯：紐約時報中文網" in content or "点击查看本文英文版" in content

                    if not saved_en or is_brand_name(saved_en) or has_trash:
                        print(f"\n[RE-FETCH] Needs repair: {local_filename}")
                        need_download = True
                    else:
                        print(f"\n[SKIP] Valid cache: {local_filename}")
                        saved_cn_match = re.search(r'<h1 class="cn-headline">(.*?)</h1>', content)
                        if saved_cn_match: final_cn_title = saved_cn_match.group(1).strip()
                        final_en_title = saved_en
                        need_download = False
                        status_tag = "CACHED"
            except:
                need_download = True

        # --- 2. Download ---
        if need_download:
            print(f"\n[DOWNLOADING] {homepage_title_hint}")
            bilingual_url = f"{clean_url}/zh-hant/dual/"

            try:
                driver.get(bilingual_url)
                time.sleep(3)

                if not is_valid_content(driver.page_source):
                    print("  -> Page invalid. Skipping.")
                    continue

                article_soup = BeautifulSoup(driver.page_source, 'html.parser')
                article_body = article_soup.find('div', class_='article-body') or \
                               article_soup.find('section', attrs={'name': 'articleBody'}) or \
                               article_soup.find('article') or \
                               article_soup.find('main')

                if article_body:
                    if not is_valid_content(article_body): continue

                    author_str = extract_author(article_soup)
                    extracted_cn = None
                    extracted_en = None

                    h1_en_tag = article_soup.find('h1', class_='en-title')
                    if h1_en_tag: extracted_en = clean_text(h1_en_tag.text)
                    if not extracted_en:
                        h1_en_head = article_soup.find('h1', class_='en-headline')
                        if h1_en_head: extracted_en = clean_text(h1_en_head.text)

                    all_h1s = article_soup.find_all('h1')
                    for h in all_h1s:
                        txt = clean_text(h.text)
                        if 'en-title' not in h.get('class', []) and re.search(r'[\u4e00-\u9fff]', txt):
                            extracted_cn = txt

                    if not extracted_en:
                        try:
                            scripts = article_soup.find_all('script', type='application/ld+json')
                            for s in scripts:
                                data = json.loads(s.string)
                                if isinstance(data, list): data = data[0]
                                if 'alternativeHeadline' in data:
                                    alt = clean_text(data['alternativeHeadline'])
                                    if alt and not is_brand_name(alt):
                                        extracted_en = alt
                                        break
                        except:
                            pass

                    if not extracted_en:
                        parts = re.split(r'\s+[-–—]\s+', driver.title)
                        for part in parts:
                            p = clean_text(part)
                            if re.match(r'^[A-Za-z0-9\s:,\.\-\?\'"’]+$', p) and not is_brand_name(p):
                                extracted_en = p
                                break

                    if extracted_cn: final_cn_title = extracted_cn
                    if extracted_en: final_en_title = extracted_en

                    for link in article_body.find_all('a'): link.unwrap()
                    header_div = article_body.find('div', class_='article-header')
                    if header_div: header_div.decompose()
                    for tag in article_body.find_all(['header', 'h1']): tag.decompose()
                    for tag in article_body.find_all(class_=re.compile(r'en[-_]?(title|headline)')): tag.decompose()
                    for tag in article_body.find_all(class_=re.compile(r'byline|meta|timestamp|date')): tag.decompose()

                    trash_texts = ["翻譯：紐約時報中文網", "點擊查看本文英文版", "点击查看本文英文版", "查看本文英文版"]
                    for trash in trash_texts:
                        found_texts = article_body.find_all(string=re.compile(re.escape(trash)))
                        for ft in found_texts:
                            parent = ft.parent
                            if parent and parent.name != 'body':
                                if len(parent.get_text().strip()) < 50:
                                    parent.decompose()
                                else:
                                    ft.replace_with("")

                    first_child = next(article_body.children, None)
                    if first_child and hasattr(first_child, 'text') and clean_text(first_child.text) == final_en_title:
                        first_child.extract()

                    safe_cn = html.escape(final_cn_title)
                    safe_en = html.escape(final_en_title)
                    safe_auth = html.escape(author_str)

                    article_html = template_content.replace('{{cn_title}}', safe_cn) \
                        .replace('{{en_title}}', safe_en) \
                        .replace('{{author}}', safe_auth) \
                        .replace('{{date}}', date_str) \
                        .replace('{{content}}', str(article_body)) \
                        .replace('{{url}}', bilingual_url)

                    with open(local_filepath, 'w', encoding='utf-8') as f:
                        f.write(article_html)

                    print(f"  -> Saved: {local_filename}")
                    status_tag = "NEW"
                else:
                    print(f"  -> No body content.")
                    continue
            except Exception as e:
                print(f"  -> Error: {e}")
                continue

        # 添加到数据列表
        articles_data.append({
            "title_cn": final_cn_title,
            "title_en": final_en_title,
            "url": f"articles/{local_filename}",
            "date": date_str,
            "tag": status_tag
        })

    driver.quit()

    # --- 3. 生成动态首页 (Data Embedded) ---
    if articles_data:
        try:
            articles_data.sort(key=lambda x: x['date'], reverse=True)
        except:
            pass

        # 将数据转换为 JSON 字符串，准备注入到 HTML 中
        json_data_str = json.dumps(articles_data, ensure_ascii=False)

        dynamic_index_html = f"""<!DOCTYPE html>
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
        li {{ padding: 25px 0; border-bottom: 1px solid var(--nyt-border); animation: fadeIn 0.5s ease; }}
        li:last-child {{ border-bottom: none; }}

        a {{ text-decoration: none; color: inherit; display: block; }}
        .article-title-cn {{ font-size: 1.4rem; font-weight: 700; margin-bottom: 4px; line-height: 1.3; color: #000; }}
        .article-title-en {{ font-size: 1.15rem; font-weight: 400; margin-bottom: 8px; line-height: 1.4; color: #444; font-style: italic; font-family: 'Georgia', serif; }}
        a:hover .article-title-cn {{ color: #00589c; }}

        .article-meta {{ font-family: sans-serif; font-size: 0.8rem; color: var(--nyt-gray); display: flex; align-items: center; }}
        .tag {{ text-transform: uppercase; font-weight: 700; font-size: 0.7rem; margin-right: 10px; color: #000; background: #eee; padding: 2px 6px; border-radius: 4px; }}

        /* Pagination Controls */
        .pagination {{ display: flex; justify-content: center; align-items: center; gap: 20px; margin-top: 40px; padding: 20px 0; border-top: 1px solid #eee; }}
        .page-btn {{ 
            padding: 8px 20px; border: 1px solid #ddd; background: white; 
            border-radius: 4px; cursor: pointer; font-family: sans-serif; font-size: 0.9rem; color: #333; 
            transition: all 0.2s;
        }}
        .page-btn:hover:not(:disabled) {{ background-color: #f5f5f5; border-color: #ccc; }}
        .page-btn:disabled {{ color: #ccc; cursor: not-allowed; border-color: #eee; }}
        .page-info {{ font-family: sans-serif; color: #666; font-size: 0.9rem; }}

        @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
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

        <ul id="article-list">
            <li style="text-align:center; padding: 40px; color: #999;">Loading articles...</li>
        </ul>

        <div class="pagination" id="pagination-controls" style="display:none;">
            <button id="prev-btn" class="page-btn">← Prev</button>
            <span id="page-info" class="page-info">Page 1</span>
            <button id="next-btn" class="page-btn">Next →</button>
        </div>

        <footer style="text-align: center; padding: 40px 20px; color: #999; font-size: 0.8rem; border-top: 1px solid #eee; margin-top: 40px;">
            <p>Generated locally for personal study.</p>
        </footer>
    </div>

    <script>
        const ARTICLES_PER_PAGE = 10;
        // 关键修改：数据直接内嵌，解决 CORS 问题
        const allArticles = /* DATA_PLACEHOLDER */; 

        let currentPage = 1;

        function initApp() {{
            if (!allArticles || allArticles.length === 0) {{
                document.getElementById('article-list').innerHTML = '<li style="text-align:center; padding: 40px;">No articles found.</li>';
                return;
            }}
            renderPage(1);
            document.getElementById('pagination-controls').style.display = 'flex';
        }}

        function renderPage(page) {{
            const start = (page - 1) * ARTICLES_PER_PAGE;
            const end = start + ARTICLES_PER_PAGE;
            const pageArticles = allArticles.slice(start, end);

            const listContainer = document.getElementById('article-list');
            listContainer.innerHTML = '';

            if (pageArticles.length === 0) {{
                listContainer.innerHTML = '<li style="text-align:center; padding: 20px;">No more articles.</li>';
                return;
            }}

            pageArticles.forEach(article => {{
                const li = document.createElement('li');
                li.innerHTML = `
                    <a href="${{article.url}}" target="_blank">
                        <div class="article-title-cn">${{article.title_cn}}</div>
                        <div class="article-title-en">${{article.title_en}}</div>
                        <div class="article-meta">
                            <span class="tag">${{article.tag}}</span>
                            <span class="date">${{article.date}}</span>
                        </div>
                    </a>
                `;
                listContainer.appendChild(li);
            }});

            // Update Controls
            currentPage = page;
            const totalPages = Math.ceil(allArticles.length / ARTICLES_PER_PAGE);

            document.getElementById('page-info').textContent = `Page ${{currentPage}} of ${{totalPages}}`;
            document.getElementById('prev-btn').disabled = currentPage === 1;
            document.getElementById('next-btn').disabled = currentPage === totalPages;

            if(window.scrollY > 200) window.scrollTo({{ top: 0, behavior: 'smooth' }});
        }}

        document.getElementById('prev-btn').addEventListener('click', () => {{
            if (currentPage > 1) renderPage(currentPage - 1);
        }});

        document.getElementById('next-btn').addEventListener('click', () => {{
            const totalPages = Math.ceil(allArticles.length / ARTICLES_PER_PAGE);
            if (currentPage < totalPages) renderPage(currentPage + 1);
        }});

        // Start
        initApp();
    </script>
</body>
</html>
"""
        # 使用 replace 注入 JSON 数据，避免 f-string 冲突
        final_html = dynamic_index_html.replace('/* DATA_PLACEHOLDER */', json_data_str)

        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(final_html)
        print(f"\nGenerated dynamic index.html with {len(articles_data)} articles embedded.")
    else:
        print("\nNo articles found.")


if __name__ == "__main__":
    scrape_nytimes()