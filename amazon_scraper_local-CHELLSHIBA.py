'''import time
import random
import re
import traceback
from bs4 import BeautifulSoup

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains


def human_type(element, text: str):
    for ch in text:
        element.send_keys(ch)
        time.sleep(random.uniform(0.03, 0.07))


def handle_popups(driver):
    try:
        dismiss_btn = driver.find_elements(
            By.CSS_SELECTOR,
            "input[data-action-type='DISMISS'], span[data-action-type='DISMISS']"
        )
        if dismiss_btn:
            dismiss_btn[0].click()
            time.sleep(1)

        no_change = driver.find_elements(
            By.XPATH, "//input[@value=\"Don't Change\"]"
        )
        if no_change:
            no_change[0].click()
            time.sleep(1)
    except:
        pass


def force_load_histogram(driver):
    """Try to wake up rating UI (not strictly needed for reviews page, but safe)."""
    try:
        print("\n➡ Step 1: Scroll to rating section")
        driver.execute_script("window.scrollBy(0, 600);")
        time.sleep(1)

        print("➡ Step 2: Hover #acrPopover")
        try:
            el = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "acrPopover"))
            )
            ActionChains(driver).move_to_element(el).perform()
            time.sleep(2)
        except:
            print("⚠ acrPopover hover failed.")

        print("➡ Step 3: Hover on star rating text")
        try:
            el2 = driver.find_element(By.CSS_SELECTOR, ".a-icon-alt")
            ActionChains(driver).move_to_element(el2).perform()
            time.sleep(2)
        except:
            print("⚠ star rating text hover failed.")
    except Exception as e:
        print("⚠ Histogram load error:", e)


def scrape_amazon(product_query: str):
    print(f"\n🔍 Scraping Amazon for: {product_query}\n")

    scraped_reviews = []
    product_title = None
    global_rating = None
    global_count = None
    histogram = {}

    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = uc.Chrome(options=options)

    try:
        # HOME
        driver.get("https://www.amazon.in/")
        time.sleep(2)
        handle_popups(driver)

        # SEARCH
        search_box = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "twotabsearchtextbox"))
        )
        search_box.click()
        human_type(search_box, product_query)
        search_box.send_keys(Keys.RETURN)
        time.sleep(3)

        # FIRST PRODUCT
        product_link = None
        products = driver.find_elements(
            By.CSS_SELECTOR,
            "a.a-link-normal.s-underline-text.s-underline-link-text.s-link-style.a-text-normal"
        )
        for p in products:
            href = p.get_attribute("href")
            if href and "/slredirect/" not in href:
                product_link = href
                break

        if not product_link:
            print("❌ No product found.")
            return

        driver.get(product_link)
        time.sleep(3)
        handle_popups(driver)

        # WAKE RATING UI (optional)
        force_load_histogram(driver)

        # MAIN PAGE PARSE
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # TITLE
        try:
            product_title = soup.select_one("#productTitle").get_text(strip=True)
        except:
            product_title = product_query

        # GLOBAL RATING
        try:
            r = soup.select_one("span[data-hook='rating-out-of-text']")
            if r:
                global_rating = float(re.search(r"[\d.]+", r.get_text()).group())
        except:
            pass

        # GLOBAL COUNT
        try:
            c = soup.select_one("#acrCustomerReviewText")
            if c:
                global_count = int(re.sub(r"[^\d]", "", c.get_text()))
        except:
            pass

        # GO TO REVIEWS PAGE
        try:
            rv_btn = driver.find_element(By.ID, "acrCustomerReviewLink")
            driver.execute_script("arguments[0].click();", rv_btn)
            time.sleep(3)
        except:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(3)

        # NOW WORK ON REVIEWS PAGE (important!)
        soup2 = BeautifulSoup(driver.page_source, "html.parser")

        # ========= SCRAPE HISTOGRAM FROM REVIEWS PAGE =========
        try:
            hist_table = soup2.find("table", id="histogramTable")
            if hist_table:
                for row in hist_table.find_all("tr"):
                    label = row.find("a") or row.find("span")
                    if not label:
                        continue
                    label_text = label.get_text(strip=True)
                    m = re.search(r"(\d)\s*star", label_text)
                    if not m:
                        continue
                    star = int(m.group(1))

                    pct_td = row.find("td", class_="a-text-right")
                    if pct_td:
                        pct_text = pct_td.get_text(strip=True).replace("%", "").strip()
                        if pct_text.isdigit():
                            histogram[star] = int(pct_text)
            else:
                print("⚠ histogramTable not found on reviews page.")
        except Exception as e:
            print("⚠ Histogram parse error:", e)

        # ========= SCRAPE REVIEWS =========
        blocks = soup2.select("div[data-hook='review']")
        for block in blocks:
            body_span = block.select_one("span[data-hook='review-body'] span")
            if body_span:
                text = body_span.get_text(strip=True)
            else:
                text = block.get_text(strip=True)

            if len(text) < 5:
                continue

            rating = 3
            r_tag = block.select_one("[data-hook='review-star-rating']")
            if r_tag:
                alt = r_tag.select_one(".a-icon-alt")
                if alt:
                    m = re.search(r"(\d+)", alt.get_text(strip=True))
                    if m:
                        try:
                            rating = int(m.group(1))
                        except:
                            pass

            scraped_reviews.append({"rating": rating, "text": text})

        # ========= PRINT OUTPUT =========
        print("\n========================")
        print("📌 PRODUCT DETAILS")
        print("========================")
        print("Title:", product_title)
        print("Rating:", global_rating)
        print("Total Reviews:", global_count)

        print("\n========================")
        print("📊 RATING PERCENTAGES (from histogram)")
        print("========================")
        if histogram:
            for s in [5, 4, 3, 2, 1]:
                print(f"{s}★: {histogram.get(s, 0)}%")
        else:
            print("No rating percentages found (histogram empty).")

        print("\n========================")
        print("📝 SAMPLE REVIEWS")
        print("========================")
        for i, r in enumerate(scraped_reviews[:10], 1):
            print(f"\n#{i} ⭐{r['rating']}\n{r['text']}")

        print("\n🎉 DONE!\n")

    except Exception as e:
        print("❌ ERROR:", e)
        traceback.print_exc()

    finally:
        try:
            driver.quit()
        except:
            pass


if __name__ == "__main__":
    q = input("Enter product name: ")
    scrape_amazon(q)'''

# OG CODE:
import time
import random
import re
import csv
from datetime import datetime
from typing import Tuple, Dict, List
from urllib.parse import urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup
from textblob import TextBlob

# fast headers
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9"
}

AUDIT_LOG = "audit_log.csv"


def log_search(query: str):
    """Append a timestamped audit log row."""
    with open(AUDIT_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([query, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])


def extract_real_link(href: str) -> str:
    """
    Some search results are redirect/ad links (sspa/click). Try to extract the inner URL.
    Return absolute link if possible.
    """
    if not href:
        return href
    # If it is already absolute and contains /dp/, return as-is
    if href.startswith("http") and "/dp/" in href:
        return href.split("?")[0]
    # If it's a redirect with query param 'url', decode it
    parsed = urlparse(href)
    qs = parse_qs(parsed.query)
    if "url" in qs:
        candidate = unquote(qs["url"][0])
        if candidate.startswith("/"):
            return "https://www.amazon.in" + candidate.split("?")[0]
        return candidate.split("?")[0]
    # if relative dp link
    if href.startswith("/"):
        return "https://www.amazon.in" + href.split("?")[0]
    return href


def search_first_product_link(query: str) -> str:
    """Return the most-likely product link from Amazon search results (or None)."""
    q = query.strip().replace(" ", "+")
    url = f"https://www.amazon.in/s?k={q}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.content, "html.parser")

    # prefer /dp/ links
    anchors = soup.select("a.a-link-normal.s-no-outline, a.a-link-normal.s-underline-text")
    for a in anchors:
        href = a.get("href")
        if not href:
            continue
        real = extract_real_link(href)
        if real and ("/dp/" in real or "/gp/" in real):
            return real

    # fallback: first anchor
    a = soup.select_one("a.a-link-normal")
    if a:
        return extract_real_link(a.get("href"))

    return None


def get_asin_from_url(url: str) -> str:
    """
    Extract ASIN from product URL (works for /dp/ASIN/ or /gp/product/ASIN).
    """
    if not url:
        return None
    m = re.search(r"/dp/([A-Z0-9]{10})", url)
    if m:
        return m.group(1)
    m = re.search(r"/gp/product/([A-Z0-9]{10})", url)
    if m:
        return m.group(1)
    # As a fallback, try to find 10-char ID
    m = re.search(r"/([A-Z0-9]{10})(?:[/?]|$)", url)
    return m.group(1) if m else None


def scrape_reviews_by_asin(asin: str, max_per_star: int = 5, max_pages: int = 10
                          ) -> Dict[int, List[dict]]:
    """
    Scrape reviews for a product ASIN using requests.
    Collect up to max_per_star reviews per star rating (5..1).
    Returns dict: {5: [review dicts], ..., 1: [...]}
    """
    collected = {5: [], 4: [], 3: [], 2: [], 1: []}
    page = 1
    user_delay = (0.6, 1.2)

    while page <= max_pages:
        reviews_url = f"https://www.amazon.in/product-reviews/{asin}/?pageNumber={page}"
        r = requests.get(reviews_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            break
        soup = BeautifulSoup(r.content, "html.parser")
        blocks = soup.select("div[data-hook='review']")
        if not blocks:
            # try alternate selector
            blocks = soup.select("div.review")
        if not blocks:
            break

        for b in blocks:
            # parse rating
            rating = None
            rating_tag = b.select_one("i[data-hook='review-star-rating'] span.a-icon-alt")
            if not rating_tag:
                rating_tag = b.select_one("span.a-icon-alt")
            if rating_tag:
                m = re.search(r"(\d+)", rating_tag.get_text(strip=True))
                if m:
                    rating = int(m.group(1))
            # parse text
            body_tag = b.select_one("span[data-hook='review-body'] span")
            if not body_tag:
                body_tag = b.select_one("span.review-text")
            text = body_tag.get_text(" ", strip=True) if body_tag else ""
            if not text or len(text) < 10 or not rating:
                continue

            # if not already full for this rating, add
            if len(collected[rating]) < max_per_star:
                polarity = TextBlob(text).sentiment.polarity
                sentiment = "Positive" if polarity > 0.1 else "Negative" if polarity < -0.1 else "Neutral"
                collected[rating].append({
                    "rating": rating,
                    "text": text,
                    "sentiment": sentiment,
                    "polarity": polarity
                })

        # stop early if collected enough for all stars
        if all(len(collected[s]) >= max_per_star for s in [5,4,3,2,1]):
            break

        page += 1
        time.sleep(random.uniform(*user_delay))

    return collected


def get_product_title_from_asin(asin: str) -> str:
    url = f"https://www.amazon.in/dp/{asin}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.content, "html.parser")
    t = soup.select_one("#productTitle")
    return t.get_text(strip=True) if t else None


def scrape_product_reviews(query: str,
                           max_per_star: int = 5,
                           max_pages: int = 10) -> Tuple[dict, str]:
    """
    Top-level function:
    - log audit
    - find product link -> asin
    - collect reviews (max_per_star per rating)
    - return dict with title, asin, reviews_by_star
    """
    log_search(query)
    link = search_first_product_link(query)
    if not link:
        return {"error": "No product found"}, None

    asin = get_asin_from_url(link)
    if not asin:
        # try parse from query page by visiting link (requests)
        r = requests.get(link, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.content, "html.parser")
        # try to find canonical /dp/ link or data-asin
        can = soup.select_one("link[rel='canonical']")
        if can and "/dp/" in can.get("href", ""):
            asin = get_asin_from_url(can.get("href"))
    if not asin:
        return {"error": "Could not determine ASIN from product link"}, link

    title = get_product_title_from_asin(asin) or query
    reviews_by_star = scrape_reviews_by_asin(asin, max_per_star=max_per_star, max_pages=max_pages)

    # save CSV for convenience
    filename = f"{re.sub(r'\\s+', '_', query.strip())}_reviews.csv"
    rows = []
    for star in [5,4,3,2,1]:
        for r in reviews_by_star.get(star, []):
            rows.append({
                "star": star,
                "rating": r["rating"],
                "text": r["text"],
                "sentiment": r["sentiment"],
                "polarity": r["polarity"]
            })
    if rows:
        with open(filename, "w", newline="", encoding="utf-8") as f:
            fieldnames = ["star", "rating", "text", "sentiment", "polarity"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    return {"title": title, "asin": asin, "reviews": reviews_by_star, "csv": filename}, link
