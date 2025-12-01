from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time


def scrape_amazon(url):
    options = Options()
    options.add_argument("--headless")  # background execution
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    driver.get(url)
    time.sleep(3)

    try:
        title = driver.find_element(By.ID, "productTitle").text.strip()
    except:
        try:
            title = driver.find_element(By.CSS_SELECTOR, "span.a-size-large").text.strip()
        except:
            title = "Title not found"

    try:
        price = driver.find_element(By.CSS_SELECTOR, "span.a-price-whole").text
    except:
        try:
            price = driver.find_element(By.CSS_SELECTOR, "span.a-offscreen").text
        except:
            price = "Price not found"

    driver.quit()
    return {"title": title, "price": price}


def scrape_flipkart(url):
    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    driver.get(url)
    time.sleep(3)

    try:
        title = driver.find_element(By.CSS_SELECTOR, "span.B_NuCI").text
    except:
        title = "Title not found"

    try:
        price = driver.find_element(By.CSS_SELECTOR, "div._30jeq3._16Jk6d").text
    except:
        price = "Price not found"

    driver.quit()
    return {"title": title, "price": price}

import schedule
import time
import json
from datetime import datetime
from scraper import scrape_amazon, scrape_flipkart


AMAZON_URL = "https://www.amazon.in/dp/B0DGH5K43K"         # change to your product
FLIPKART_URL = "https://www.flipkart.com/p/itm72f3faf77e924"  # change to your product


def run_job():
    print("\n📌 Running scraper...")

    amazon = scrape_amazon(AMAZON_URL)
    flipkart = scrape_flipkart(FLIPKART_URL)

    data = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Amazon Title": amazon["title"],
        "Amazon Price": amazon["price"],
        "Flipkart Title": flipkart["title"],
        "Flipkart Price": flipkart["price"]
    }

    try:
        existing = json.load(open("price_history.json", "r", encoding="utf-8"))
    except:
        existing = []

    existing.append(data)
    json.dump(existing, open("price_history.json", "w", encoding="utf-8"), indent=4)

    print("✔ Saved → price_history.json")
    print(f"Amazon: {amazon['price']} | Flipkart: {flipkart['price']}")


schedule.every(10).minutes.do(run_job)

print("🚀 Scheduler Started — Scraping every 10 minutes\n")
print("Do not close this window\n")

while True:
    schedule.run_pending()
    time.sleep(1)