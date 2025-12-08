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

# [重要] 必须设为 True 运行一次，以重新处理所有 HTML 文件
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
    # 修复模板中的首页链接，使其指向根目录
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


# --- 新增功能：扫描所有本地文件并重建 articles.json ---
def rebuild_json_index():
    print("\n[INDEXING] Scanning local files to rebuild articles.json...")
    articles_data = []

    if not os.path.exists(ARTICLES_DIR):
        print("No articles directory found.")
        return

    # 遍历 articles 目录
    for root, dirs, files in os.walk(ARTICLES_DIR):
        for file in files:
            if file.endswith(".html"):
                full_path = os.path.join(root, file)

                # 读取文件提取元数据
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    soup = BeautifulSoup(content, 'html.parser')

                    # 提取标题 (cn)
                    cn_title = ""
                    h1_cn = soup.find('h1', class_='cn-headline') or soup.find('div', class_='article-title-cn')
                    if h1_cn: cn_title = clean_text(h1_cn.get_text())

                    # 提取标题 (en)
                    en_title = ""
                    h1_en = soup.find('h1', class_='en-headline') or soup.find('div', class_='article-title-en')
                    if h1_en: en_title = clean_text(h1_en.get_text())

                    # 提取日期 (尝试从路径或内容提取)
                    # 路径格式通常为: articles/YYYYMMDD/slug.html
                    path_parts = os.path.normpath(full_path).split(os.sep)
                    date_str = ""

                    # 尝试从文件夹名称获取日期 (假设文件夹名是 YYYYMMDD)
                    for part in path_parts:
                        if re.match(r'^\d{8}$', part):
                            date_str = f"{part[:4]}-{part[4:6]}-{part[6:]}"
                            break

                    # 如果路径没日期，尝试从文件内容获取
                    if not date_str:
                        date_meta = soup.find('meta', attrs={'name': 'date'})
                        if date_meta: date_str = date_meta.get('content')

                    if not date_str:
                        # 最后手段：文件修改时间
                        ts = os.path.getmtime(full_path)
                        date_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')

                    # 生成相对 Web 路径 (必须是正斜杠)
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

    # 按日期倒序排序
    articles_data.sort(key=lambda x: x['date'], reverse=True)

    # 保存 JSON
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
    today_folder = today_str.replace('-', '')  # YYYYMMDD

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
        if any(x in href for x in ['/2023', '/2024', '/2022']): continue  # 可选：过滤旧年份
        if href in unique_links: continue
        if 'cn.nytimes.com' in href and not href.startswith('http'): continue

        unique_links[href] = title_hint
        absolute_url = urljoin(base_url, href)
        clean_url = absolute_url.split('?')[0].rstrip('/')
        if clean_url.endswith('/zh-hant'): clean_url = clean_url[:-len('/zh-hant')]

        # Date Extraction & Path Setup
        date_match = re.search(r'/(\d{4})(\d{2})(\d{2})/', clean_url)
        if date_match:
            article_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
            article_folder = article_date.replace('-', '')
        else:
            article_date = today_str
            article_folder = today_folder

        # 目标文件夹
        target_dir = os.path.join(ARTICLES_DIR, article_folder)
        os.makedirs(target_dir, exist_ok=True)

        slug = clean_url.split('/')[-1]
        local_filename = f"{slug}.html"
        local_filepath = os.path.join(target_dir, local_filename)

        # 检查是否已存在
        if os.path.exists(local_filepath) and not FORCE_UPDATE:
            # 简单检查文件有效性
            try:
                with open(local_filepath, 'r', encoding='utf-8') as f:
                    if is_valid_content(f.read()) and HOME_URL in f.read():
                        print(f"[SKIP] Exists: {local_filename}")
                        continue
            except:
                pass

        # 下载逻辑
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
                # 提取元数据
                author_str = extract_author(article_soup)
                final_cn = title_hint
                final_en = ""

                # 尝试获取英文标题
                h1_en = article_soup.find('h1', class_='en-title') or article_soup.find('h1', class_='en-headline')
                if h1_en: final_en = clean_text(h1_en.text)

                # 如果没找到英文标题，尝试从网页标题分割
                if not final_en:
                    parts = re.split(r'\s+[-–—]\s+', driver.title)
                    for p in parts:
                        p = clean_text(p)
                        if re.match(r'^[A-Za-z0-9\s:,\.\-\?\'"’]+$', p) and not is_brand_name(p):
                            final_en = p
                            break

                # 注入 class
                target_elements = article_body.find_all('p') + article_body.find_all('div', class_='article-paragraph')
                for tag in target_elements:
                    txt = tag.get_text().strip()
                    if not txt: continue
                    if re.search(r'[\u4e00-\u9fff]', txt):
                        tag['class'] = tag.get('class', []) + ['cn-p']
                    else:
                        tag['class'] = tag.get('class', []) + ['en-p']

                # 清理垃圾元素
                for link in article_body.find_all('a'): link.unwrap()
                for tag in article_body.find_all(['header', 'h1']): tag.decompose()
                trash_texts = ["翻譯：紐約時報中文網", "點擊查看本文英文版", "点击查看本文英文版"]
                for trash in trash_texts:
                    for ft in article_body.find_all(string=re.compile(re.escape(trash))):
                        if ft.parent: ft.parent.decompose()

                # 生成 HTML
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

    # 最后一步：重建索引 JSON
    rebuild_json_index()


if __name__ == "__main__":
    scrape_nytimes()