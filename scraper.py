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
ARTICLES_PER_PAGE = 10

# [重要] 设为 True 运行一次，以修复旧文章缺失的语言标签
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

    # Index Head
    index_html_head = f"""<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>纽约时报双语版 - NYTimes Bilingual</title><style>:root{{--nyt-black:#121212;--nyt-gray:#727272;--nyt-border:#e2e2e2;--bg-color:#f8f9fa}}body{{font-family:'Georgia','Times New Roman',serif;background-color:var(--bg-color);color:var(--nyt-black);margin:0;padding:0;line-height:1.5}}.app-container{{max-width:800px;margin:0 auto;background:#fff;min-height:100vh;box-shadow:0 0 20px rgba(0,0,0,0.05);padding-bottom:40px}}header{{padding:40px 20px 20px 20px;text-align:center;margin-bottom:20px;border-bottom:4px double #000}}.masthead{{font-family:'Georgia',serif;font-size:3rem;margin:0;font-weight:900;letter-spacing:-1px;line-height:1;color:#000;margin-bottom:10px}}.sub-masthead{{font-family:sans-serif;font-size:1.1rem;font-weight:700;color:#333;margin-bottom:15px;letter-spacing:1px}}.date-line{{border-top:1px solid #ddd;padding:8px 0;font-family:sans-serif;font-size:0.85rem;color:#555;display:flex;justify-content:space-between;text-transform:uppercase}}ul{{list-style:none;padding:0 30px;margin:0}}li{{padding:25px 0;border-bottom:1px solid var(--nyt-border)}}li:last-child{{border-bottom:none}}a{{text-decoration:none;color:inherit;display:block}}.article-title-cn{{font-size:1.4rem;font-weight:700;margin-bottom:4px;line-height:1.3;color:#000}}.article-title-en{{font-size:1.15rem;font-weight:400;margin-bottom:8px;line-height:1.4;color:#444;font-style:italic;font-family:'Georgia',serif}}a:hover .article-title-cn{{color:#00589c}}.article-meta{{font-family:sans-serif;font-size:0.8rem;color:var(--nyt-gray);display:flex;align-items:center}}.tag{{text-transform:uppercase;font-weight:700;font-size:0.7rem;margin-right:10px;color:#000;background:#eee;padding:2px 6px;border-radius:4px}}
    .pagination {{ display: flex; justify-content: center; align-items: center; gap: 15px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }}
    .page-link {{ padding: 8px 15px; border: 1px solid #ddd; border-radius: 4px; text-decoration: none; color: #333; font-size: 0.9rem; font-family: sans-serif; }}
    .page-link:hover {{ background-color: #f5f5f5; border-color: #ccc; }}
    .page-link.disabled {{ color: #ccc; pointer-events: none; border-color: #eee; }}
    .page-info {{ font-size: 0.9rem; color: #666; font-family: sans-serif; }}
    </style></head><body><div class="app-container"><header><div class="masthead">The New York Times</div><div class="sub-masthead">纽约时报双语版</div><div class="date-line"><span>{datetime.date.today().strftime("%A, %B %d, %Y")}</span><span>Daily Selection</span></div></header><ul>"""

    list_items = []
    unique_links = {}
    article_pattern = re.compile(r'/\d{8}/')
    processed_articles = 0

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
        date_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}" if date_match else today_str

        slug = clean_url.split('/')[-1]
        local_filename = f"{slug}.html"
        local_filepath = os.path.join(output_dir, local_filename)

        final_cn_title = homepage_title_hint
        final_en_title = ""
        need_download = True

        # Check Local File
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
                    # 检查是否有 cn-p 类名，如果没有，说明是旧版文件，需要重新处理
                    has_classes = 'cn-p' in content or 'en-p' in content
                    has_trash = "翻譯：紐約時報中文網" in content

                    if not saved_en or is_brand_name(saved_en) or has_trash or not has_classes:
                        print(f"\n[RE-FETCH] Updating file (Missing Classes/Bad Title): {local_filename}")
                        need_download = True
                    else:
                        print(f"\n[SKIP] Valid cache: {local_filename}")
                        saved_cn_match = re.search(r'<h1 class="cn-headline">(.*?)</h1>', content)
                        if saved_cn_match: final_cn_title = saved_cn_match.group(1).strip()
                        final_en_title = saved_en
                        need_download = False
                        list_items.append(
                            f'<li><a href="{os.path.join("articles", local_filename)}"><div class="article-title-cn">{final_cn_title}</div><div class="article-title-en">{final_en_title}</div><div class="article-meta"><span class="tag">CACHED</span><span class="date">{date_str}</span></div></a></li>')
                        processed_articles += 1
                        continue
            except:
                need_download = True

        # Download
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

                    # Titles Extraction
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

                    # --- 核心修复：注入语言类名 (Class Injection) ---
                    # 遍历正文段落，区分中英文并添加 class
                    for p in article_body.find_all('p'):
                        # 检查段落文字
                        txt = p.get_text().strip()
                        if not txt: continue

                        # 简单的启发式：如果有中文字符，就是中文段落
                        if re.search(r'[\u4e00-\u9fff]', txt):
                            # 使用 class 列表操作避免覆盖原有 class
                            current_classes = p.get('class', [])
                            if 'cn-p' not in current_classes:
                                p['class'] = current_classes + ['cn-p']
                        else:
                            # 否则认为是英文
                            current_classes = p.get('class', [])
                            if 'en-p' not in current_classes:
                                p['class'] = current_classes + ['en-p']

                    # Body Cleanup
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

                    list_items.append(
                        f'<li><a href="{os.path.join("articles", local_filename)}"><div class="article-title-cn">{final_cn_title}</div><div class="article-title-en">{final_en_title}</div><div class="article-meta"><span class="tag">NEW</span><span class="date">{date_str}</span></div></a></li>')
                    processed_articles += 1
                else:
                    print(f"  -> No body content.")
            except Exception as e:
                print(f"  -> Error: {e}")

    driver.quit()

    # Generate Pagination
    if len(list_items) > 0:
        chunks = [list_items[i:i + ARTICLES_PER_PAGE] for i in range(0, len(list_items), ARTICLES_PER_PAGE)]
        total_pages = len(chunks)
        for i, chunk in enumerate(chunks):
            page_num = i + 1
            filename = 'index.html' if page_num == 1 else f'index_{page_num}.html'
            page_list_html = "\n".join(chunk)

            prev_html = ""
            if page_num > 1:
                prev_file = 'index.html' if page_num == 2 else f'index_{page_num - 1}.html'
                prev_html = f'<a href="{prev_file}" class="page-link">← Prev</a>'
            else:
                prev_html = '<span class="page-link disabled">← Prev</span>'

            next_html = ""
            if page_num < total_pages:
                next_file = f'index_{page_num + 1}.html'
                next_html = f'<a href="{next_file}" class="page-link">Next →</a>'
            else:
                next_html = '<span class="page-link disabled">Next →</span>'

            pagination_html = f'<div class="pagination">{prev_html}<span class="page-info">Page {page_num} of {total_pages}</span>{next_html}</div>'
            full_html = f"{index_html_head}<ul>{page_list_html}</ul>{pagination_html}<footer style='text-align:center;padding:40px;color:#999;font-size:0.8rem;margin-top:20px;'>Generated locally.</footer></div></body></html>"

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(full_html)
        print(f"\nDone! Generated {total_pages} pages for {len(list_items)} articles.")
    else:
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(f"{index_html_head}<ul><li>No articles found.</li></ul></div></body></html>")
        print("\nNo articles found.")


if __name__ == "__main__":
    scrape_nytimes()