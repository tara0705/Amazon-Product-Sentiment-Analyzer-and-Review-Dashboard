import requests
from bs4 import BeautifulSoup
import csv
import time
import re

def scrape_reviews(product_url, max_pages=5):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }

    all_reviews = []

    for page in range(1, max_pages + 1):
        print(f"📄 Scraping page {page}...")

        page_url = product_url.replace("/dp/", "/product-reviews/") + f"?pageNumber={page}"
        res = requests.get(page_url, headers=headers)

        if res.status_code != 200:
            print("❌ Page load error:", res.status_code)
            break

        soup = BeautifulSoup(res.text, "html.parser")
        review_blocks = soup.select("div[data-hook='review']")

        if not review_blocks:
            print("⚠ No reviews found on this page.")
            break

        for block in review_blocks:
            # Rating
            rating_tag = block.select_one("i[data-hook='review-star-rating'] span")
            rating = int(re.search(r"(\d+)", rating_tag.get_text(strip=True)).group()) if rating_tag else None

            # Title
            title_tag = block.select_one("a[data-hook='review-title'] span")
            title = title_tag.get_text(strip=True) if title_tag else ""

            # Review text
            body_tag = block.select_one("span[data-hook='review-body'] span")
            body = body_tag.get_text(strip=True) if body_tag else ""

            all_reviews.append([rating, title, body])

        time.sleep(1)

    # Save to CSV
    with open("amazon_reviews.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Rating", "Title", "Review"])
        writer.writerows(all_reviews)

    print(f"\n🎉 {len(all_reviews)} reviews saved to amazon_reviews.csv\n")


if __name__ == "__main__":
    product_url = input("Paste Amazon Product URL: ").strip()
    scrape_reviews(product_url)