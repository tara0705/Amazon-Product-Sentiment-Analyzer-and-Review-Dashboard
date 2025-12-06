import os
import time
import random
import re
import traceback
from collections import Counter, defaultdict
from datetime import datetime
from dateutil import parser as date_parser

from bs4 import BeautifulSoup

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from sklearn.feature_extraction.text import TfidfVectorizer

# Sentiment analyzer: try VADER first, fallback to simple polarity via TextBlob-like
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _SENT_ANALYZER = SentimentIntensityAnalyzer()
    _SENT_BACKEND = "vader"
except Exception:
    _SENT_ANALYZER = None
    _SENT_BACKEND = None


# ----------------- Helper functions -----------------
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
            try:
                dismiss_btn[0].click()
                time.sleep(1)
            except:
                pass

        no_change = driver.find_elements(
            By.XPATH, "//input[@value=\"Don't Change\"]"
        )
        if no_change:
            try:
                no_change[0].click()
                time.sleep(1)
            except:
                pass
    except Exception:
        pass


def force_load_histogram(driver):
    """Attempt to wake rating UI. Non-fatal if fails."""
    try:
        driver.execute_script("window.scrollBy(0, 600);")
        time.sleep(1)
        try:
            el = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "acrPopover"))
            )
            ActionChains(driver).move_to_element(el).perform()
            time.sleep(1)
        except Exception:
            pass

        try:
            el2 = driver.find_element(By.CSS_SELECTOR, ".a-icon-alt")
            ActionChains(driver).move_to_element(el2).perform()
            time.sleep(1)
        except Exception:
            pass
    except Exception:
        pass


def safe_get_text(el):
    try:
        return el.get_text(strip=True)
    except:
        try:
            return el.text.strip()
        except:
            return ""


def parse_review_date(date_str: str):
    """Try robust parsing of review date text like '12 March 2024' or 'Reviewed in India on 12 March 2024'."""
    if not date_str:
        return None
    # Remove common prefixes
    date_str = re.sub(r"Reviewed in.*on", "", date_str, flags=re.I).strip()
    date_str = date_str.replace("Reviewed in", "").replace("on", "").strip()
    try:
        dt = date_parser.parse(date_str, dayfirst=True)
        return dt.date()
    except Exception:
        # fallback: try extracting dd mmm yyyy
        m = re.search(r"(\d{1,2}\s+\w+\s+\d{4})", date_str)
        if m:
            try:
                dt = date_parser.parse(m.group(1), dayfirst=True)
                return dt.date()
            except:
                return None
    return None


# ----------------- Scraper -----------------
def scrape_amazon(product_query: str, headless=False, max_reviews=200):
    """
    Returns:
        meta: dict with product_title, global_rating, global_count, histogram
        reviews: list of dicts {rating:int, text:str, date:date or None}
    """
    print(f"\nScraping Amazon.in for: {product_query}")
    options = uc.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # some stealth
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = uc.Chrome(options=options)
    meta = {"product_title": None, "global_rating": None, "global_count": None, "histogram": {}}
    reviews = []

    try:
        driver.get("https://www.amazon.in/")
        time.sleep(2)
        handle_popups(driver)

        # Search
        search_box = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "twotabsearchtextbox"))
        )
        search_box.click()
        human_type(search_box, product_query)
        search_box.send_keys(Keys.RETURN)
        time.sleep(2 + random.random() * 2)

        # Find first product link (safer selector)
        product_link = None
        product_anchors = driver.find_elements(By.CSS_SELECTOR, "a.a-link-normal.s-underline-text.s-underline-link-text.s-link-style.a-text-normal")
        for p in product_anchors:
            href = p.get_attribute("href")
            if href and "/slredirect/" not in href:
                product_link = href
                break

        # fallback: broader anchor selection
        if not product_link:
            anchors = driver.find_elements(By.CSS_SELECTOR, "a.a-link-normal.a-text-normal")
            for a in anchors:
                href = a.get_attribute("href")
                if href and "/gp/" in href:
                    product_link = href
                    break

        if not product_link:
            print("No product link found on search page.")
            return meta, reviews

        # Open product page
        driver.get(product_link)
        time.sleep(2 + random.random() * 2)
        handle_popups(driver)
        force_load_histogram(driver)
        time.sleep(1)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Title
        try:
            meta["product_title"] = soup.select_one("#productTitle").get_text(strip=True)
        except:
            meta["product_title"] = product_query

        # Global rating
        try:
            r = soup.select_one("span[data-hook='rating-out-of-text']")
            if r:
                meta["global_rating"] = float(re.search(r"[\d.]+", r.get_text()).group())
        except:
            pass

        # Global count
        try:
            c = soup.select_one("#acrCustomerReviewText")
            if c:
                meta["global_count"] = int(re.sub(r"[^\d]", "", c.get_text()))
        except:
            pass

        # Try to click reviews link
        try:
            rv_btn = driver.find_element(By.ID, "acrCustomerReviewLink")
            driver.execute_script("arguments[0].click();", rv_btn)
            time.sleep(2 + random.random() * 2)
        except Exception:
            # fallback: scroll to reviews
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.75)")
            time.sleep(2)

        # Now iterate review pages until max or no more
        scraped = 0
        page = 1
        while scraped < max_reviews:
            soup2 = BeautifulSoup(driver.page_source, "html.parser")

            # histogram (if on this page)
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
                            try:
                                meta["histogram"][star] = int(re.sub(r"[^\d]", "", pct_text))
                            except:
                                pass
            except Exception:
                pass

            # reviews blocks
            blocks = soup2.select("div[data-hook='review']")
            if not blocks:
                # amazon sometimes uses different class, try alternative
                blocks = soup2.select("div.review")

            if not blocks:
                # nothing to scrape on this page
                pass

            for block in blocks:
                if scraped >= max_reviews:
                    break
                # rating
                rating = None
                try:
                    r_tag = block.select_one("[data-hook='review-star-rating'], [data-hook='cmps-review-star-rating']")
                    if r_tag:
                        alt = r_tag.get_text()
                        m = re.search(r"(\d+(\.\d+)?)", alt)
                        if m:
                            rating = int(float(m.group(1)))
                except:
                    pass
                if rating is None:
                    # fallback
                    rating = 0

                # text
                body_span = block.select_one("span[data-hook='review-body'] span")
                if body_span:
                    text = body_span.get_text(strip=True)
                else:
                    # sometimes textual content is direct
                    text = safe_get_text(block)
                # date
                date_text = ""
                try:
                    date_el = block.select_one("span[data-hook='review-date']")
                    if date_el:
                        date_text = date_el.get_text(strip=True)
                except:
                    pass
                parsed_date = parse_review_date(date_text)

                if text and len(text) > 3:
                    reviews.append({"rating": rating, "text": text, "date": parsed_date})
                    scraped += 1

            # Move to next reviews page if exists
            try:
                # Amazon review pagination link labelled "Next"
                nxt = driver.find_elements(By.CSS_SELECTOR, "li.a-last a")
                if nxt:
                    driver.execute_script("arguments[0].click();", nxt[0])
                    time.sleep(2 + random.random() * 2)
                    page += 1
                    continue
                else:
                    # sometimes a different structure; try find rel="next"
                    link = driver.find_elements(By.CSS_SELECTOR, "a[aria-label='Next page'], a[aria-label='next page']")
                    if link:
                        driver.execute_script("arguments[0].click();", link[0])
                        time.sleep(2 + random.random() * 2)
                        page += 1
                        continue
                    else:
                        break
            except Exception:
                break

        print(f"Scraped {len(reviews)} reviews (requested {max_reviews}).")

    except Exception as e:
        print("Scrape error:", e)
        traceback.print_exc()
    finally:
        try:
            driver.quit()
        except:
            pass

    return meta, reviews


# ----------------- Analytics -----------------
def analyze_reviews(meta, reviews, output_dir="output", top_n_keywords=20):
    os.makedirs(output_dir, exist_ok=True)

    df = pd.DataFrame(reviews)
    if df.empty:
        print("No reviews to analyze.")
        return

    # Normalize date column to datetime
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    else:
        df["date"] = pd.NaT

    # Sentiment: VADER if available
    def get_sentiment_scores(text):
        if _SENT_BACKEND == "vader" and _SENT_ANALYZER:
            return _SENT_ANALYZER.polarity_scores(text)
        else:
            # fallback: naive sentiment by counting positive/negative words (very rough)
            # but we will at least provide a 'compound' placeholder using simple heuristic
            words = re.findall(r"\w+", text.lower())
            pos_words = {"good", "great", "excellent", "best", "love", "lovely", "nice", "happy", "fantastic", "amazing"}
            neg_words = {"bad", "worst", "disappointed", "disappointing", "poor", "terrible", "awful", "hate"}
            pos = sum(w in pos_words for w in words)
            neg = sum(w in neg_words for w in words)
            compound = (pos - neg) / (len(words) + 1)
            return {"neg": float(neg), "neu": float(max(0, len(words) - pos - neg)), "pos": float(pos), "compound": float(compound)}

    s_scores = df["text"].apply(get_sentiment_scores)
    s_df = pd.DataFrame(list(s_scores))
    df = pd.concat([df.reset_index(drop=True), s_df.reset_index(drop=True)], axis=1)

    # Label sentiment buckets
    def bucket_from_compound(comp):
        if comp >= 0.05:
            return "positive"
        elif comp <= -0.05:
            return "negative"
        else:
            return "neutral"

    df["sentiment"] = df["compound"].apply(bucket_from_compound)

    # Save raw reviews to CSV
    out_csv = os.path.join(output_dir, "reviews.csv")
    df.to_csv(out_csv, index=False)
    print(f"Saved scraped reviews -> {out_csv}")

    # Sentiment distribution
    sentiment_counts = df["sentiment"].value_counts().to_dict()

    # Rating distribution
    rating_counts = df["rating"].value_counts().sort_index().to_dict()

    # Rating trend: average rating per month
    df["month"] = df["date"].dt.to_period("M")
    rating_trend = df.dropna(subset=["month"]).groupby("month")["rating"].mean()
    # fill if empty
    if rating_trend.empty and not df["date"].isna().all():
        try:
            # group by date string fallback
            rating_trend = df.groupby(df["date"].dt.to_period("M"))["rating"].mean()
        except:
            rating_trend = pd.Series(dtype=float)

    # Keyword extraction: TF-IDF top features
    texts = df["text"].astype(str).tolist()
    tfidf = TfidfVectorizer(max_df=0.85, min_df=2, stop_words="english", ngram_range=(1,2))
    try:
        X = tfidf.fit_transform(texts)
        sums = np.asarray(X.sum(axis=0)).ravel()
        terms = tfidf.get_feature_names_out()
        term_scores = list(zip(terms, sums))
        term_scores = sorted(term_scores, key=lambda x: x[1], reverse=True)
        top_keywords = term_scores[:top_n_keywords]
    except Exception:
        top_keywords = []

    # Frequency table (top words)
    all_words = []
    for t in texts:
        # naive tokenization, remove non-words and stop words
        tokens = re.findall(r"\w{3,}", t.lower())
        all_words.extend(tokens)
    c = Counter(all_words)
    top_words = c.most_common(30)

    # Wordcloud
    try:
        from wordcloud import WordCloud
        wc = WordCloud(width=1200, height=600, collocations=False, background_color="white")
        wc_img = wc.generate(" ".join(all_words))
        wc_path = os.path.join(output_dir, "wordcloud.png")
        wc_img.to_file(wc_path)
        print(f"Saved wordcloud -> {wc_path}")
    except Exception as e:
        print("WordCloud generation failed:", e)
        wc_path = None

    # Plots: sentiment pie, rating histogram, rating trend
    plt.figure(figsize=(6,6))
    labels = list(sentiment_counts.keys())
    sizes = [sentiment_counts[k] for k in labels]
    plt.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=140)
    plt.title("Sentiment Distribution")
    plt.tight_layout()
    sentiment_path = os.path.join(output_dir, "sentiment_pie.png")
    plt.savefig(sentiment_path)
    plt.close()
    print(f"Saved sentiment pie -> {sentiment_path}")

    # rating histogram
    plt.figure(figsize=(8,4))
    ratings_sorted = sorted(rating_counts.items())
    xs = [r for r, _ in ratings_sorted]
    ys = [cnt for _, cnt in ratings_sorted]
    plt.bar(xs, ys)
    plt.xlabel("Rating (stars)")
    plt.ylabel("Count")
    plt.title("Rating Counts")
    plt.tight_layout()
    rating_hist_path = os.path.join(output_dir, "rating_hist.png")
    plt.savefig(rating_hist_path)
    plt.close()
    print(f"Saved rating histogram -> {rating_hist_path}")

    # rating trend (line)
    if not rating_trend.empty:
        plt.figure(figsize=(10,4))
        xt = [str(p) for p in rating_trend.index.astype(str)]
        yt = rating_trend.values
        plt.plot(xt, yt, marker="o")
        plt.xticks(rotation=45)
        plt.xlabel("Month")
        plt.ylabel("Average Rating")
        plt.title("Average Rating Trend (by month)")
        plt.tight_layout()
        trend_path = os.path.join(output_dir, "rating_trend.png")
        plt.savefig(trend_path)
        plt.close()
        print(f"Saved rating trend -> {trend_path}")
    else:
        trend_path = None

    # Save summary insights
    summary_lines = []
    summary_lines.append(f"Product: {meta.get('product_title')}")
    summary_lines.append(f"Global rating: {meta.get('global_rating')} | Global review count: {meta.get('global_count')}")
    summary_lines.append("")
    summary_lines.append("Sentiment distribution:")
    for k, v in sentiment_counts.items():
        summary_lines.append(f"  {k}: {v}")
    summary_lines.append("")
    summary_lines.append("Rating counts:")
    for k, v in rating_counts.items():
        summary_lines.append(f"  {k}★: {v}")
    summary_lines.append("")
    summary_lines.append("Top TF-IDF keywords:")
    for t, s in top_keywords:
        summary_lines.append(f"  {t} ({s:.4f})")
    summary_lines.append("")
    summary_lines.append("Top words (frequency):")
    for w, cnt in top_words[:30]:
        summary_lines.append(f"  {w}: {cnt}")
    summary_text = "\n".join(summary_lines)
    summary_path = os.path.join(output_dir, "summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_text)
    print(f"Saved summary -> {summary_path}")

    # Also return analysis objects
    results = {
        "df": df,
        "sentiment_counts": sentiment_counts,
        "rating_counts": rating_counts,
        "top_keywords": top_keywords,
        "top_words": top_words,
        "wordcloud_path": wc_path,
        "sentiment_plot": sentiment_path,
        "rating_hist_plot": rating_hist_path,
        "rating_trend_plot": trend_path,
        "summary_path": summary_path
    }
    return results


# ----------------- CLI -----------------
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Amazon review scraper + analytics (India)")
    parser.add_argument("query", help="Product search query (quoted)")
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    parser.add_argument("--max", type=int, default=200, help="Max reviews to scrape (default 200)")
    parser.add_argument("--out", default="output", help="Output directory")
    args = parser.parse_args()

    meta, reviews = scrape_amazon(args.query, headless=args.headless, max_reviews=args.max)
    if not reviews:
        print("No reviews scraped. Exiting.")
        return

    results = analyze_reviews(meta, reviews, output_dir=args.out)
    print("\nDone. Outputs in directory:", args.out)
    print("Summary file:", results.get("summary_path"))
    if results.get("wordcloud_path"):
        print("Wordcloud image:", results.get("wordcloud_path"))
    if results.get("rating_trend_plot"):
        print("Rating trend plot:", results.get("rating_trend_plot"))


if __name__ == "__main__":
    main()