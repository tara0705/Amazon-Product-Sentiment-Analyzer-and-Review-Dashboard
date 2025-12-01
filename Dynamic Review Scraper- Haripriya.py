from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import json
import time

# Amazon Scraper Function
def scrape_amazon(url):
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    driver.get(url)
    time.sleep(4)

    data = {}

    try:
        data['product_name'] = driver.find_element(By.ID, "productTitle").text.strip()
    except:
        data['product_name'] = "Not Found"

    try:
        data['price'] = driver.find_element(By.CSS_SELECTOR, "span.a-price-whole").text.strip()
    except:
        data['price'] = "Not Found"

    try:
        data['rating'] = driver.find_element(By.CSS_SELECTOR, "span.a-icon-alt").text.strip()
    except:
        data['rating'] = "Not Found"

    reviews = []
    try:
        review_elements = driver.find_elements(By.CSS_SELECTOR, "span.review-text-content span")
        for r in review_elements[:5]:
            reviews.append(r.text.strip())
    except:
        pass

    data['reviews'] = reviews
    driver.quit()
    return data


# Flipkart Scraper Function
def scrape_flipkart(url):
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    driver.get(url)
    time.sleep(4)

    data = {}

    try:
        close_btn = driver.find_element(By.CSS_SELECTOR, "button._2KpZ6l._2doB4z")
        close_btn.click()
    except:
        pass

    try:
        data['product_name'] = driver.find_element(By.CSS_SELECTOR, "span.B_NuCI").text.strip()
    except:
        data['product_name'] = "Not Found"

    try:
        data['price'] = driver.find_element(By.CSS_SELECTOR, "div._30jeq3._16Jk6d").text.strip()
    except:
        data['price'] = "Not Found"

    try:
        data['rating'] = driver.find_element(By.CSS_SELECTOR, "div._3LWZlK").text.strip()
    except:
        data['rating'] = "Not Found"

    reviews = []
    try:
        review_elements = driver.find_elements(By.CSS_SELECTOR, "div.t-ZTKy")
        for r in review_elements[:5]:
            reviews.append(r.text.strip())
    except:
        pass

    data['reviews'] = reviews
    driver.quit()
    return data


# Main Execution
amazon_url = input("Enter Amazon Product URL: ")
flipkart_url = input("Enter Flipkart Product URL: ")

amazon_data = scrape_amazon(amazon_url)
flipkart_data = scrape_flipkart(flipkart_url)

final_data = {
    "Amazon_Product": amazon_data,
    "Flipkart_Product": flipkart_data
}

# Save data to JSON
with open("scraped_product_data.json", "w", encoding="utf-8") as file:
    json.dump(final_data, file, indent=4, ensure_ascii=False)

print("\nScraping completed successfully! 🎉")
print("Data saved in scraped_product_data.json file.")