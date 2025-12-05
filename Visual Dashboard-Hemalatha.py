import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud
import pandas as pd

# =====================================================
# 1. PIE CHART – Sentiment Distribution
# =====================================================
def plot_sentiment_pie(df):
    sentiment_counts = df['sentiment'].value_counts()

    plt.figure(figsize=(5, 5))
    plt.pie(sentiment_counts,
            labels=sentiment_counts.index,
            autopct='%1.1f%%',
            startangle=90)

    plt.title("Sentiment Distribution")
    plt.show()


# =====================================================
# 2. BAR CHART – Rating Distribution
# =====================================================
def plot_rating_bar(df):
    plt.figure(figsize=(6, 4))
    sns.countplot(x=df["rating"])

    plt.title("Rating Distribution")
    plt.xlabel("Rating (1-5)")
    plt.ylabel("Count")
    plt.show()


# =====================================================
# 3. LINE CHART – Sentiment Trend Over Time
#    (Assumes your team adds 'date' column)
# =====================================================
def plot_sentiment_trend(df):
    if "date" not in df.columns:
        print("⚠ No 'date' column found, skipping trend chart.")
        return

    trend = df.groupby("date")["sentiment_score"].mean()

    plt.figure(figsize=(7, 4))
    trend.plot()

    plt.title("Sentiment Trend Over Time")
    plt.xlabel("Date")
    plt.ylabel("Avg Sentiment Score")
    plt.grid(True)
    plt.show()


# =====================================================
# 4. WORDCLOUD – Most Frequent Words in Reviews
# =====================================================
def generate_wordcloud(df):
    text = " ".join(df["clean_text"].tolist())

    wc = WordCloud(width=800, height=400,
                   background_color="white").generate(text)

    plt.figure(figsize=(10, 5))
    plt.imshow(wc, interpolation='bilinear')
    plt.axis('off')
    plt.title("Word Cloud")
    plt.show()


# =====================================================
# 5. FILTER FUNCTION – For Dashboard Buttons
# =====================================================
def filter_reviews(df, rating=None, sentiment=None):
    filtered = df.copy()

    if rating:
        filtered = filtered[filtered["rating"] == rating]

    if sentiment:
        filtered = filtered[filtered["sentiment"] == sentiment]

    return filtered


# =====================================================
# 6. MASTER FUNCTION – Team Will Call This
# =====================================================
def show_dashboard(df):
    print("\n📌 Generating Dashboard...")

    plot_sentiment_pie(df)
    plot_rating_bar(df)
    plot_sentiment_trend(df)
    generate_wordcloud(df)

    print("\n🎉 Dashboard Completed!")


# =====================================================
# DEMO (only for testing)
# =====================================================
if __name__ == "__main__":
    sample = pd.DataFrame({
        "rating": [5, 4, 5, 3, 1, 4],
        "sentiment": ["positive", "positive", "neutral", "negative", "negative", "positive"],
        "sentiment_score": [0.7, 0.8, 0.1, -0.3, -0.6, 0.9],
        "clean_text": [
            "good product", "very useful", "okay item",
            "bad material", "worst quality", "excellent"
        ]
    })

    show_dashboard(sample)
#SCRAPPER CODE
import time
import random
import re
import traceback
import pandas as pd
from bs4 import BeautifulSoup

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys


def human_type(element, text: str):
    for ch in text:
        element.send_keys(ch)
        time.sleep(random.uniform(0.03, 0.07))


def scrape_amazon(product_query: str):
    print(f"\n🔍 Scraping Amazon for: {product_query}\n")

    scraped_reviews = []

    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = uc.Chrome(options=options)

    try:
        driver.get("https://www.amazon.in/")
        time.sleep(2)

        search_box = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "twotabsearchtextbox"))
        )
        search_box.click()
        human_type(search_box, product_query)
        search_box.send_keys(Keys.RETURN)
        time.sleep(3)

        products = driver.find_elements(
            By.CSS_SELECTOR,
            "a.a-link-normal.s-underline-text.s-underline-link-text.s-link-style.a-text-normal"
        )

        if not products:
            print("❌ No products found.")
            return None

        # Open first product
        product_link = products[0].get_attribute("href")
        driver.get(product_link)
        time.sleep(3)

        # Go to reviews page
        try:
            rv = driver.find_element(By.ID, "acrCustomerReviewLink")
            rv.click()
            time.sleep(3)
        except:
            print("⚠ Couldn't open reviews page.")

        soup = BeautifulSoup(driver.page_source, "html.parser")
        blocks = soup.select("div[data-hook='review']")

        for block in blocks:
            body_span = block.select_one("span[data-hook='review-body'] span")
            text = body_span.get_text(strip=True) if body_span else ""

            rating = block.select_one("i[data-hook='review-star-rating']")
            if rating:
                rating = int(rating.text[0])
            else:
                rating = None

            if len(text) > 5:
                scraped_reviews.append({"rating": rating, "text": text})

        df = pd.DataFrame(scraped_reviews)
        df.to_csv("raw_reviews.csv", index=False)
        print("\n📁 Saved raw reviews → raw_reviews.csv")

        return df

    except Exception as e:
        print("❌ ERROR:", e)
        traceback.print_exc()

    finally:
        driver.quit()

import pandas as pd
from amazon_scraper import scrape_amazon
from preprocess_sentiment import clean_reviews, apply_sentiment
from visual_dashboard import show_dashboard

print("\n📌 AMAZON REVIEW ANALYSIS PIPELINE\n")

product = input("Enter product name: ")

# Step 1 — Scrape
df_raw = scrape_amazon(product)

if df_raw is None or df_raw.empty:
    print("❌ No reviews scraped. Exiting.")
    exit()

# Step 2 — Clean
df_clean = clean_reviews(df_raw)

# Step 3 — Sentiment Analysis
df_final = apply_sentiment(df_clean)

df_final.to_csv("final_processed_reviews.csv", index=False)
print("\n📁 Saved final data → final_processed_reviews.csv")

# Step 4 — Dashboard
show_dashboard(df_final)

