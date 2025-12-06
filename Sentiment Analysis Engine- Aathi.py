import time
import random
import re
import traceback
from bs4 import BeautifulSoup

# Selenium + driver
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# ---- Sentiment (VADER only) ----
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
vader = SentimentIntensityAnalyzer()
# --------------------------------


def human_type(element, text: str):
    for ch in text:
        element.send_keys(ch)
        time.sleep(random.uniform(0.03, 0.07))


def handle_popups(driver):
    try:
        btns = driver.find_elements(
            By.CSS_SELECTOR,
            "input[data-action-type='DISMISS'], span[data-action-type='DISMISS']"
        )
        if btns:
            btns[0].click()
            time.sleep(1)

        no_change = driver.find_elements(By.XPATH, "//input[@value=\"Don't Change\"]")
        if no_change:
            no_change[0].click()
            time.sleep(1)
    except:
        pass


def analyze_sentiment(text):
    v = vader.polarity_scores(text)
    compound = v["compound"]

    if compound >= 0.05:
        sentiment = "Positive"
    elif compound <= -0.05:
        sentiment = "Negative"
    else:
        sentiment = "Neutral"

    return compound, sentiment


def scrape_amazon(product_query: str):
    print(f"\n🔍 Searching Amazon for: {product_query}\n")

    reviews_output = []

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    try:
        driver.get("https://www.amazon.in/")
        time.sleep(2)
        handle_popups(driver)

        search_box = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "twotabsearchtextbox"))
        )
        search_box.click()
        human_type(search_box, product_query)
        search_box.send_keys(Keys.RETURN)
        time.sleep(3)

        # First product
        products = driver.find_elements(
            By.CSS_SELECTOR,
            "a.a-link-normal.s-underline-text.s-underline-link-text.s-link-style.a-text-normal"
        )
        link = None
        for p in products:
            href = p.get_attribute("href")
            if href and "/slredirect/" not in href:
                link = href
                break

        if not link:
            print("❌ No product found.")
            return

        driver.get(link)
        time.sleep(3)
        handle_popups(driver)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        try:
            title = soup.select_one("#productTitle").get_text(strip=True)
        except:
            title = product_query

        try:
            r = soup.select_one("span[data-hook='rating-out-of-text']")
            global_rating = float(re.search(r"[\d.]+", r.get_text()).group())
        except:
            global_rating = None

        try:
            count = soup.select_one("#acrCustomerReviewText")
            total_reviews = int(re.sub(r"[^\d]", "", count.get_text()))
        except:
            total_reviews = None

        # Go to review page
        try:
            driver.find_element(By.ID, "acrCustomerReviewLink").click()
            time.sleep(3)
        except:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)

        soup2 = BeautifulSoup(driver.page_source, "html.parser")

        # -------- SCRAPE REVIEWS --------
        blocks = soup2.select("div[data-hook='review']")

        for block in blocks:
            body_tag = block.select_one("span[data-hook='review-body'] span")
            text = body_tag.get_text(strip=True) if body_tag else ""
            if len(text) < 5:
                continue

            rating = 3
            tag = block.select_one("[data-hook='review-star-rating'] .a-icon-alt")
            if tag:
                m = re.search(r"(\d)", tag.get_text(strip=True))
                if m:
                    rating = int(m.group(1))

            compound, sentiment = analyze_sentiment(text)

            reviews_output.append({
                "rating": rating,
                "review": text,
                "compound": compound,
                "sentiment": sentiment,
            })

        # -------- OUTPUT --------
        print("\n====================")
        print(" PRODUCT DETAILS")
        print("====================")
        print("Title:", title)
        print("Rating:", global_rating)
        print("Total Reviews:", total_reviews)

        print("\n====================")
        print(" REVIEWS + SENTIMENT")
        print("====================")

        for i, r in enumerate(reviews_output[:10], 1):
            print(f"\n#{i} ⭐{r['rating']} | {r['sentiment']}")
            print("Review:", r['review'])
            print("Compound Score:", r['compound'])

        print("\n🎉 DONE!")

    except Exception as e:
        print("❌ ERROR:", e)
        traceback.print_exc()

    finally:
        driver.quit()


if __name__ == "__main__":
    q = input("Enter product name: ")
    scrape_amazon(q)