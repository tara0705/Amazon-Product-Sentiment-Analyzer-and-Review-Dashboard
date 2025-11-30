import time
import random
import traceback
import re
from collections import Counter

from flask import Flask, request, jsonify
from flask_cors import CORS
from textblob import TextBlob
from bs4 import BeautifulSoup
from flask_caching import Cache
from rapidfuzz import process, fuzz

# Selenium
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

app = Flask(__name__)
CORS(app)

# Cache
app.config["CACHE_TYPE"] = "SimpleCache"
app.config["CACHE_DEFAULT_TIMEOUT"] = 3600
cache = Cache(app)
SEARCH_HISTORY_INDEX = {}

# =========================================================
# SENTIMENT HELPER (Used only for sample review table)
# =========================================================
def get_sentiment(text):
    """We use this only for displaying sentiment in the sample reviews table."""
    text_lower = text.lower()

    negative_keywords = [
        "bad", "poor", "worst", "terrible", "disappointed", "slow", "broken",
        "damage", "damaged", "waste", "useless", "refund", "heating",
        "issue", "issues", "problem", "fault", "doesn't", "does not work"
    ]

    if any(word in text_lower for word in negative_keywords):
        return "Negative"

    polarity = TextBlob(text).sentiment.polarity

    if polarity > 0.10:
        return "Positive"
    elif polarity < -0.05:
        return "Negative"
    return "Neutral"


# =========================================================
# SCRAPER
# =========================================================
def human_type(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.04, 0.08))


def handle_popups(driver):
    try:
        dismiss_btn = driver.find_elements(
            By.CSS_SELECTOR,
            "input[data-action-type='DISMISS'], span[data-action-type='DISMISS']",
        )
        if dismiss_btn:
            dismiss_btn[0].click()
            time.sleep(1)

        dont_change_btn = driver.find_elements(
            By.XPATH, "//input[@value=\"Don't Change\"]"
        )
        if dont_change_btn:
            dont_change_btn[0].click()
            time.sleep(1)
    except:
        pass


def scrape_amazon_realtime(product_query):
    print(f"🔍 Searching for: {product_query}")

    scraped_data = []
    title = None
    global_rating = None
    global_count = None
    histogram = {}

    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = None
    try:
        driver = uc.Chrome(options=options)

        # Homepage
        driver.get("https://www.amazon.in/")
        time.sleep(2)
        handle_popups(driver)

        # Search
        box = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "twotabsearchtextbox"))
        )
        box.click()
        human_type(box, product_query)
        box.send_keys(Keys.RETURN)
        time.sleep(3)

        # Find product result
        product_link = None
        results = driver.find_elements(
            By.CSS_SELECTOR,
            "a.a-link-normal.s-underline-text.s-underline-link-text.s-link-style.a-text-normal",
        )
        for res in results:
            href = res.get_attribute("href")
            if href and "/slredirect/" not in href:
                product_link = href
                break

        if not product_link:
            return [], None, None, None, {}

        # Open product page
        driver.get(product_link)
        time.sleep(3)
        handle_popups(driver)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Title
        try:
            title = soup.select_one("#productTitle").get_text(strip=True)
        except:
            title = product_query

        # Global rating
        try:
            r_el = soup.select_one("span[data-hook='rating-out-of-text']")
            if r_el:
                rt = r_el.get_text(strip=True)
                m = re.search(r"(\d+(\.\d+)?)", rt)
                if m:
                    global_rating = float(m.group(1))
        except:
            pass

        # Global review count
        try:
            c_el = soup.select_one("#acrCustomerReviewText")
            if c_el:
                count = re.sub(r"[^\d]", "", c_el.get_text(strip=True))
                if count:
                    global_count = int(count)
        except:
            pass

        # Histogram (star percentages)
        try:
            hist = soup.select_one("#histogramTable")
            if hist:
                rows = hist.select("tr")
                for row in rows:
                    label = row.select_one("a, span")
                    if not label: continue
                    star_text = label.get_text(strip=True)
                    star_match = re.search(r"(\d)\s*star", star_text)
                    if not star_match: continue

                    star = int(star_match.group(1))
                    pct_el = row.select_one("td.a-text-right")
                    if pct_el:
                        pct = pct_el.get_text(strip=True).replace("%", "")
                        histogram[star] = int(pct)
        except:
            pass

        print("📊 Histogram:", histogram)

        # Go to review section
        try:
            review_link = driver.find_element(By.ID, "acrCustomerReviewLink")
            driver.execute_script("arguments[0].click();", review_link)
            time.sleep(4)
        except:
            pass

        soup2 = BeautifulSoup(driver.page_source, "html.parser")
        review_blocks = soup2.select(
            "div[data-hook='review'], div[data-hook='review-collapsed'], div.a-section.review"
        )

        # Scrape sample reviews
        for block in review_blocks:
            txt = ""
            b1 = block.select_one("span[data-hook='review-body'] span")
            if b1:
                txt = b1.get_text(strip=True)

            if not txt:
                txt = block.get_text(strip=True)

            if len(txt) < 5:
                continue

            # extract star rating for table (not used in sentiment)
            rating = 3
            r_icon = block.select_one("[data-hook='review-star-rating']")
            if r_icon:
                alt = r_icon.select_one(".a-icon-alt")
                if alt:
                    m = re.search(r"(\d+)", alt.get_text(strip=True))
                    if m:
                        rating = int(m.group(1))

            scraped_data.append({"text": txt, "rating": rating})

    except Exception as e:
        print("❌ Scraper Error:", e)
    finally:
        if driver:
            driver.quit()

    return scraped_data, title, global_rating, global_count, histogram


# =========================================================
# PROCESSING — FINAL SENTIMENT BASED ON HISTOGRAM
# =========================================================
def process_data(raw_reviews, product_query, global_rating, global_count, histogram):
    # sample reviews table sentiment
    processed_reviews = []
    for i, r in enumerate(raw_reviews):
        processed_reviews.append({
            "id": i + 1,
            "text": r["text"],
            "sentiment": get_sentiment(r["text"]),
            "rating": r["rating"],
            "date": "Verified Amazon.in"
        })

    # Total reviews from Amazon
    total_reviews = global_count if global_count else len(raw_reviews)

    # -----------------------------
    # USE HISTOGRAM FOR SENTIMENT
    # -----------------------------
    if histogram and total_reviews:
        pct5 = histogram.get(5, 0)
        pct4 = histogram.get(4, 0)
        pct3 = histogram.get(3, 0)
        pct2 = histogram.get(2, 0)
        pct1 = histogram.get(1, 0)

        positive = int(total_reviews * ((pct5 + pct4) / 100))
        neutral = int(total_reviews * (pct3 / 100))
        negative = int(total_reviews * ((pct2 + pct1) / 100))

        # fix rounding mismatch
        diff = total_reviews - (positive + neutral + negative)
        if diff != 0:
            positive += diff
    else:
        # fallback only
        positive = int(total_reviews * 0.7)
        neutral = int(total_reviews * 0.2)
        negative = total_reviews - positive - neutral

    # Trend (mock)
    trend = []
    base = total_reviews // 5
    for m in ["Jan", "Feb", "Mar", "Apr", "May"]:
        trend.append({
            "month": m,
            "positive": int(base * random.uniform(0.8, 1.2)),
            "negative": int(base * random.uniform(0.8, 1.2)),
            "neutral": int(base * random.uniform(0.8, 1.2))
        })

    # Word frequency
    all_text = " ".join([r["text"] for r in raw_reviews]).lower()
    words = [w for w in all_text.split() if len(w) > 4]

    word_freq = [{"word": w[0].title(), "count": w[1] * 4}
                 for w in Counter(words).most_common(5)]

    return {
        "totalReviews": total_reviews,
        "averageRating": global_rating if global_rating else 0,
        "sentimentCounts": {
            "positive": positive,
            "neutral": neutral,
            "negative": negative,
        },
        "trendData": trend,
        "wordFrequency": word_freq,
        "reviews": processed_reviews[:8]
    }


# =========================================================
# API ROUTE
# =========================================================
@app.route("/api/analyze_product", methods=["GET"])
def analyze_product():
    try:
        product_query = request.args.get("product", "").strip()
        if not product_query:
            return jsonify({"message": "No product provided"}), 400

        data_cached = SEARCH_HISTORY_INDEX.get(product_query)
        if data_cached:
            return jsonify(data_cached)

        raw_reviews, title, rating, count, histogram = scrape_amazon_realtime(product_query)

        result = process_data(raw_reviews, product_query, rating, count, histogram)
        result["productName"] = title
        result["recommendations"] = [
            {"id": 1, "name": "Best Sellers"},
            {"id": 2, "name": "Top Rated Accessories"},
        ]

        SEARCH_HISTORY_INDEX[product_query] = result

        return jsonify(result)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"message": "Server error", "error": str(e)}), 500


# =========================================================
# RUN SERVER
# =========================================================

if __name__ == "__main__":
    print("🚀 Starting Flask backend on http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)