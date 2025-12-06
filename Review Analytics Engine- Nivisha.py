import time
import random
import re
import traceback
from bs4 import BeautifulSoup

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException, SessionNotCreatedException


# ============ HUMAN TYPING ============
def human_type(element, text: str):
    for ch in text:
        element.send_keys(ch)
        time.sleep(random.uniform(0.03, 0.07))


# ============ POPUP HANDLER ============
def handle_popups(driver):
    try:
        dismiss = driver.find_elements(By.CSS_SELECTOR, "[data-action-type='DISMISS']")
        if dismiss:
            dismiss[0].click()
            time.sleep(1)

        dont_change = driver.find_elements(By.XPATH, "//input[@value=\"Don't Change\"]")
        if dont_change:
            dont_change[0].click()
            time.sleep(1)
    except:
        pass


# ============ DRIVER CREATION ============
def create_driver():
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Prevent destructor error
    uc.Chrome.__del__ = lambda self: None

    try:
        return uc.Chrome(version_main=142, options=options)
    except SessionNotCreatedException as e:
        print("❌ ChromeDriver version mismatch.")
        raise e


# ============ EXTRACT HISTOGRAM (COMBINED) ============
def extract_histogram(soup):
    histogram = {}

    # --- Method 1: New Amazon 2024–2025 Layout ---
    bars = soup.select("div[data-hook='histogram-bar']")
    if bars:
        for bar in bars:
            star_label = bar.select_one("span.a-size-base")
            pct_label = bar.select_one("span.a-size-base.a-text-right")

            if star_label and pct_label:
                m = re.search(r"(\d+)", star_label.get_text(strip=True))
                pct = pct_label.get_text(strip=True).replace("%", "").strip()
                if m and pct.isdigit():
                    histogram[int(m.group(1))] = int(pct)

    # --- Method 2: Old Histogram Table ---
    if not histogram:
        table = soup.find("table", id="histogramTable")
        if table:
            for row in table.find_all("tr"):
                label = row.find("a") or row.find("span")
                if label:
                    m = re.search(r"(\d)\s*star", label.text)
                    if m:
                        star = int(m.group(1))
                        pct_td = row.find("td", class_="a-text-right")
                        if pct_td:
                            pct = pct_td.text.replace("%", "").strip()
                            if pct.isdigit():
                                histogram[star] = int(pct)

    # --- Method 3: Fallback Compact Style ---
    if not histogram:
        labels = soup.select("span[data-hook='histogram-bar-label']")
        percents = soup.select("span[data-hook='histogram-bar-percentage']")
        if len(labels) == len(percents) and len(labels) > 0:
            for l, p in zip(labels, percents):
                m = re.search(r"(\d+)", l.text.strip())
                pct = p.text.strip().replace("%", "")
                if m and pct.isdigit():
                    histogram[int(m.group(1))] = int(pct)

    return histogram


# ============ MAIN SCRAPER ============
def scrape_amazon(product_query: str):
    print(f"\n🔍 Searching Amazon for: {product_query}\n")

    driver = None

    try:
        driver = create_driver()

        # Open Amazon
        driver.get("https://www.amazon.in/")
        time.sleep(2)
        handle_popups(driver)

        # Search box
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

        product_link = None
        for p in products:
            href = p.get_attribute("href")
            if href and "/slredirect/" not in href:
                product_link = href
                break

        if not product_link:
            print("❌ No product found.")
            return

        driver.get(product_link)
        time.sleep(2)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Product title
        try:
            title = soup.select_one("#productTitle").get_text(strip=True)
        except:
            title = product_query

        print("📄 Product Title:", title)

        # Move to review page
        try:
            link = driver.find_element(By.ID, "acrCustomerReviewLink")
            driver.execute_script("arguments[0].click();", link)
            time.sleep(3)
        except:
            pid = re.search(r"/dp/([A-Za-z0-9]+)", product_link)
            if pid:
                driver.get(f"https://www.amazon.in/product-reviews/{pid.group(1)}")
                time.sleep(3)

        soup_review = BeautifulSoup(driver.page_source, "html.parser")

        # ----------------- Extract Histogram -----------------
        histogram = extract_histogram(soup_review)

        print("\n📊 RATING HISTOGRAM")
        print("---------------------------")
        for s in [5, 4, 3, 2, 1]:
            print(f"{s}★: {histogram.get(s, 0)}%")

        print("\n🎉 DONE!")

    except Exception as e:
        print("❌ ERROR:", e)
        traceback.print_exc()

    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


# ============ RUN ============

if __name__ == "__main__":
    q = input("Enter product name: ")
    scrape_amazon(q)