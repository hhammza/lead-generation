from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
import requests
import time
import re
import sys
import json
from urllib.parse import urljoin

def log(msg):
    print(msg, flush=True)

def clean_text(text):
    if not text:
        return None
    text = re.sub(r'[\uE000-\uF8FF]', '', text)
    return " ".join(text.split())

def extract_emails(text):
    if not text:
        return []
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return list(set(emails))

def scrape_website_emails(url):
    if not url:
        return []
    emails = set()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    pages = [url, urljoin(url, "/contact"), urljoin(url, "/contact-us"), urljoin(url, "/about"), urljoin(url, "/about-us")]
    for page_url in pages:
        try:
            response = requests.get(page_url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")
            emails.update(extract_emails(soup.get_text(" ", strip=True)))
        except Exception:
            continue
    return list(emails)

def run(query, target_results, output_file):
    maps_url = "https://www.google.com/maps/search/" + query.replace(" ", "+")
    business_links = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        maps_page = browser.new_page()

        log(f"[INFO] Opening Google Maps for: {query}")
        maps_page.goto(maps_url, timeout=60000)
        maps_page.wait_for_selector('div[role="feed"]')
        time.sleep(3)

        log(f"[INFO] Collecting up to {target_results} results...")
        feed = maps_page.locator('div[role="feed"]')
        previous_count = 0
        no_change = 0

        while len(business_links) < target_results and no_change < 6:
            cards = maps_page.locator('a.hfpxzc')
            count = cards.count()
            for i in range(count):
                link = cards.nth(i).get_attribute("href")
                if link and link not in business_links:
                    business_links.append(link)
                    log(f"[FOUND] {len(business_links)}")
                    if len(business_links) >= target_results:
                        break
            if count == previous_count:
                no_change += 1
            else:
                no_change = 0
                previous_count = count
            feed.evaluate("(element) => element.scrollBy(0, 3000)")
            time.sleep(2)

        log(f"[INFO] Collected {len(business_links)} business URLs")

        detail_page = browser.new_page()
        data = []

        for index, link in enumerate(business_links, start=1):
            log(f"[SCRAPING {index}/{len(business_links)}]")
            try:
                detail_page.goto(link, timeout=60000)
                time.sleep(3)

                def get_text(selector):
                    try:
                        return clean_text(detail_page.locator(selector).first.inner_text())
                    except:
                        return None

                def get_attr(selector, attr):
                    try:
                        return detail_page.locator(selector).first.get_attribute(attr)
                    except:
                        return None

                name = get_text("h1")
                category = get_text("button.DkEaL")
                address = get_text('button[data-item-id="address"]')
                phone = get_text('button[data-item-id^="phone"]')
                website = get_attr('a[data-item-id="authority"]', "href")
                rating = get_text("div.F7nice span")
                reviews = get_text("span.hh2c6")
                emails = scrape_website_emails(website)

                data.append({
                    "Business Name": name,
                    "Category": category,
                    "Address": address,
                    "Phone": phone,
                    "Website": website,
                    "Email": ", ".join(emails),
                    "Rating": rating,
                    "Reviews": reviews
                })
                log(f"[OK] {name}")
            except Exception as e:
                log(f"[ERROR] {e}")

        browser.close()

    df = pd.DataFrame(data)
    df.to_csv(output_file, index=False, encoding="utf-8-sig")
    log(f"[DONE] Saved {len(data)} leads to {output_file}")

if __name__ == "__main__":
    args = json.loads(sys.argv[1])
    run(args["query"], int(args["target_results"]), args["output_file"])
