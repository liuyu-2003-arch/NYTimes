import requests
from bs4 import BeautifulSoup
import re
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from urllib.parse import urljoin

# --- CONFIGURATION ---
CHROME_DRIVER_PATH = '/Users/yuliu/PycharmProjects/NYTimes/chromedriver' 

def get_page_source_with_selenium(url):
    """
    Uses Selenium to load a page, allowing JavaScript to execute,
    and returns the final page source.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    service = Service(CHROME_DRIVER_PATH)
    driver = None
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print(f"Fetching page with Selenium: {url}")
        driver.get(url)
        time.sleep(5) 
        return driver.page_source
    finally:
        if driver:
            driver.quit()

def scrape_nytimes():
    output_dir = 'articles'
    os.makedirs(output_dir, exist_ok=True)

    base_url = "https://cn.nytimes.com"
    homepage_url = f"{base_url}/zh-hant/"
    
    try:
        homepage_html = get_page_source_with_selenium(homepage_url)
        if not homepage_html:
            print("Failed to get homepage source with Selenium.")
            return
    except Exception as e:
        print(f"An error occurred with Selenium: {e}")
        print("Please ensure ChromeDriver is installed and the CHROME_DRIVER_PATH is correct.")
        return

    soup = BeautifulSoup(homepage_html, 'html.parser')
    all_links = soup.find_all('a')

    index_html_content = """
    <!DOCTYPE html><html lang="zh-Hant"><head><meta charset="UTF-8"><title>纽约时报双语文章 (本地保存版)</title>
    <style>body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;line-height:1.6;margin:2em auto;max-width:800px;padding:0 1em;color:#333}h1{color:#000;border-bottom:2px solid #eee;padding-bottom:.5em}ul{list-style-type:decimal;padding-left:2em}li{margin-bottom:1em}a{text-decoration:none;color:#00589c;font-weight:bold}a:hover{text-decoration:underline;color:#003d6b}</style>
    </head><body><h1>纽约时报双语文章 (本地保存版)</h1><ul>
    """

    unique_links = {}
    article_pattern = re.compile(r'/\d{8}/')
    processed_articles = 0

    for link in all_links:
        href = link.get('href', '')
        title = link.text.strip()

        # --- URL Cleaning and Validation ---
        if not (href and title and article_pattern.search(href) and href not in unique_links):
            continue
        
        # Skip malformed hrefs that contain the domain name
        if 'cn.nytimes.com' in href and not href.startswith('http'):
            print(f"\\nSkipping malformed href: {href}")
            continue

        # Create a full, absolute URL from the href
        absolute_url = urljoin(base_url, href)

        # Skip links with future dates (likely placeholders)
        if re.search(r'/(202[5-9]|203\d)\d{4}/', absolute_url):
             print(f"\\nSkipping likely placeholder article: {title}")
             continue

        unique_links[href] = title
        print(f"\\nFound article: {title}")
        
        # --- Bilingual URL Construction ---
        # 1. Clean the base URL
        article_base_url = absolute_url.split('?')[0].strip('/')
        # 2. Remove a potential /zh-hant suffix
        if article_base_url.endswith('/zh-hant'):
            article_base_url = article_base_url[:-len('/zh-hant')]
        # 3. Construct the final bilingual URL
        bilingual_url = f"{article_base_url}/zh-hant/dual/"

        try:
            print(f"  -> Attempting to download from: {bilingual_url}")
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            article_response = requests.get(bilingual_url, headers=headers)
            
            if article_response.status_code == 404:
                print("  -> No bilingual version available (404 Not Found). Skipping.")
                continue
            
            article_response.raise_for_status()
            time.sleep(1)

            # --- Save the bilingual article content ---
            slug = article_base_url.split('/')[-1]
            local_filename = f"{slug}.html"
            local_filepath = os.path.join(output_dir, local_filename)

            article_soup = BeautifulSoup(article_response.text, 'html.parser')
            article_body = article_soup.find('div', class_='article-body') or article_soup.find('article')

            if article_body:
                page_title_tag = article_soup.find('h1')
                page_title = page_title_tag.text.strip() if page_title_tag else title

                article_html = f'''
                <!DOCTYPE html><html lang="zh-Hant"><head><meta charset="UTF-8"><title>{page_title}</title>
                <style>
                    body {{ font-family: Georgia, serif; line-height: 1.8; margin: 2em auto; max-width: 700px; padding: 0 1em; }}
                    h1 {{ text-align: center; border-bottom: 1px solid #ccc; padding-bottom: 0.5em; margin-bottom: 2em;}}
                    .dual-english p {{ color: #333; }}
                    .dual-chinese p {{ color: #00589c; margin-bottom: 2em; }}
                </style>
                </head><body><h1>{page_title}</h1>{str(article_body)}</body></html>'''

                with open(local_filepath, 'w', encoding='utf-8') as f:
                    f.write(article_html)
                print(f"  -> Successfully saved to {local_filepath}")
                
                index_html_content += f'<li><a href="{local_filepath}" target="_blank">{page_title}</a></li>\\n'
                processed_articles += 1
            else:
                print(f"  -> Could not find article body in the page. Skipping.")

        except requests.exceptions.RequestException as e:
            print(f"  -> Failed to download or process article {title}: {e}")
        except Exception as e:
            print(f"  -> An unexpected error occurred: {e}")

    index_html_content += "</ul></body></html>"

    if processed_articles > 0:
        try:
            with open('index.html', 'w', encoding='utf-8') as f:
                f.write(index_html_content)
            print(f"\\nSuccessfully created index.html linking to {processed_articles} local bilingual articles.")
        except IOError as e:
            print(f"Error writing to index.html: {e}")
    else:
        print("\\nCould not find and process any bilingual articles.")

if __name__ == "__main__":
    scrape_nytimes()
