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
ARTICLES_DIR = 'articles'
JSON_DB_FILE = 'articles.json'
HOME_URL = "https://nytimes.324893.xyz"

# [重要] 除非你需要强制刷新所有文件，否则保持为 False
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
        content = f.read()
    content = content.replace('href="index.html"', f'href="{HOME_URL}"')
    content = content.replace('href="../index.html"', f'href="{HOME_URL}"')
    content = content.replace('href="./index.html"', f'href="{HOME_URL}"')
    return content


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


def is_valid_content(soup_or_text):
    text = str(soup_or_text)
    invalid_markers = ["Page Not Found", "頁面未找到", "页面未找到"]
    for marker in invalid_markers:
        if marker in text: return False
    return True


# --- 重建索引 ---
def rebuild_json_index():
    print("\n[INDEXING] Scanning local files to rebuild articles.json...")
    articles_data = []

    if not os.path.exists(ARTICLES_DIR):
        print("No articles directory found.")
        return

    for root, dirs, files in os.walk(ARTICLES_DIR):
        for file in files:
            if file.endswith(".html"):
                full_path = os.path.join(root, file)

                try:
                    # 快速读取，不做深度解析以节省时间，只提取必要信息
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    soup = BeautifulSoup(content, 'html.parser')

                    cn_title = ""
                    h1_cn = soup.find('h1', class_='cn-headline') or soup.find('div', class_='article-title-cn')
                    if h1_cn: cn_title = clean_text(h1_cn.get_text())

                    en_title = ""
                    h_en = soup.find('h1', class_='en-headline') or \
                           soup.find('h2', class_='en-headline') or \
                           soup.find('div', class_='article-title-en') or \
                           soup.find('h1', class_='en-title')

                    if h_en: en_title = clean_text(h_en.get_text())

                    # 日期提取
                    path_parts = os.path.normpath(full_path).split(os.sep)
                    date_str = ""
                    for part in path_parts:
                        if re.match(r'^\d{8}$', part):
                            date_str = f"{part[:4]}-{part[4:6]}-{part[6:]}"
                            break

                    if not date_str:
                        date_meta = soup.find('meta', attrs={'name': 'date'})
                        if date_meta: date_str = date_meta.get('content')

                    if not date_str:
                        ts = os.path.getmtime(full_path)
                        date_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')

                    web_path = os.path.relpath(full_path, start='.').replace('\\', '/')

                    if cn_title:
                        articles_data.append({
                            "title_cn": cn_title,
                            "title_en": en_title,
                            "url": web_path,
                            "date": date_str,
                            "tag": "ARCHIVE"
                        })
                except Exception as e:
                    print(f"Skipping broken file {file}: {e}")

    articles_data.sort(key=lambda x: x['date'], reverse=True)

    with open(JSON_DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(articles_data, f, ensure_ascii=False, indent=2)

    print(f"Index rebuilt. Total articles: {len(articles_data)}")


def scrape_nytimes():
    os.makedirs(ARTICLES_DIR, exist_ok=True)
    template_content = load_template()
    if not template_content: return

    base_url = "https://cn.nytimes.com"
    homepage_url = f"{base_url}/zh-hant/"
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    today_folder = today_str.replace('-', '')

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
    article_pattern = re.compile(r'/\d{8}/')
    unique_links = {}

    print(f"Found {len(all_links)} links. Filtering...")

    for link in all_links:
        href = link.get('href', '')
        title_hint = clean_text(link.text)

        if not (href and title_hint and article_pattern.search(href)): continue
        if any(x in href for x in ['/2023', '/2024', '/2022']): continue
        if href in unique_links: continue
        if 'cn.nytimes.com' in href and not href.startswith('http'): continue

        unique_links[href] = title_hint
        absolute_url = urljoin(base_url, href)
        clean_url = absolute_url.split('?')[0].rstrip('/')
        if clean_url.endswith('/zh-hant'): clean_url = clean_url[:-len('/zh-hant')]

        date_match = re.search(r'/(\d{4})(\d{2})(\d{2})/', clean_url)
        if date_match:
            article_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
            article_folder = article_date.replace('-', '')
        else:
            article_date = today_str
            article_folder = today_folder

        target_dir = os.path.join(ARTICLES_DIR, article_folder)
        os.makedirs(target_dir, exist_ok=True)

        slug = clean_url.split('/')[-1]
        local_filename = f"{slug}.html"
        local_filepath = os.path.join(target_dir, local_filename)

        # --- 核心修改：极速跳过逻辑 ---
        # 只要文件存在且大小大于0，直接跳过，不再进行任何内容检查
        if os.path.exists(local_filepath) and not FORCE_UPDATE:
            if os.path.getsize(local_filepath) > 0:
                print(f"[SKIP] Exists: {local_filename}")
                continue

        # 如果没跳过，才开始下载
        print(f"\n[DOWNLOADING] {title_hint}")
        bilingual_url = f"{clean_url}/zh-hant/dual/"
        try:
            driver.get(bilingual_url)
            time.sleep(3)

            if not is_valid_content(driver.page_source):
                print("  -> Page invalid.")
                continue

            article_soup = BeautifulSoup(driver.page_source, 'html.parser')
            article_body = article_soup.find('div', class_='article-body') or \
                           article_soup.find('section', attrs={'name': 'articleBody'}) or \
                           article_soup.find('article') or \
                           article_soup.find('main')

            if article_body and is_valid_content(article_body):
                author_str = extract_author(article_soup)
                final_cn = title_hint
                final_en = ""

                h1_en = article_soup.find('h1', class_='en-title') or article_soup.find('h1', class_='en-headline')
                if h1_en: final_en = clean_text(h1_en.text)

                if not final_en:
                    parts = re.split(r'\s+[-–—]\s+', driver.title)
                    for p in parts:
                        p = clean_text(p)
                        if re.match(r'^[A-Za-z0-9\s:,\.\-\?\'"’]+$', p) and not is_brand_name(p):
                            final_en = p
                            break

                target_elements = article_body.find_all('p') + article_body.find_all('div', class_='article-paragraph')
                for tag in target_elements:
                    txt = tag.get_text().strip()
                    if not txt: continue
                    if re.search(r'[\u4e00-\u9fff]', txt):
                        tag['class'] = tag.get('class', []) + ['cn-p']
                    else:
                        tag['class'] = tag.get('class', []) + ['en-p']

                for link in article_body.find_all('a'): link.unwrap()
                for tag in article_body.find_all(['header', 'h1']): tag.decompose()
                trash_texts = ["翻譯：紐約時報中文網", "點擊查看本文英文版", "点击查看本文英文版"]
                for trash in trash_texts:
                    for ft in article_body.find_all(string=re.compile(re.escape(trash))):
                        if ft.parent: ft.parent.decompose()

                safe_cn = html.escape(final_cn)
                safe_en = html.escape(final_en)
                safe_auth = html.escape(author_str)

                full_html = template_content.replace('{{cn_title}}', safe_cn) \
                    .replace('{{en_title}}', safe_en) \
                    .replace('{{author}}', safe_auth) \
                    .replace('{{date}}', article_date) \
                    .replace('{{content}}', str(article_body)) \
                    .replace('{{url}}', bilingual_url)

                with open(local_filepath, 'w', encoding='utf-8') as f:
                    f.write(full_html)
                print(f"  -> Saved to {article_folder}/{local_filename}")

        except Exception as e:
            print(f"  -> Error: {e}")

    driver.quit()
    rebuild_json_index()


if __name__ == "__main__":
    scrape_nytimes()