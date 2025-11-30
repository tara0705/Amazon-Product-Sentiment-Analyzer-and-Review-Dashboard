import streamlit as st
import pandas as pd
import altair as alt
from amazon_scraper_local import scrape_product_reviews
#streamlit run streamlit_app.py
st.set_page_config(page_title="Amazon Review Analyzer", layout="wide")
st.title("Amazon Review Analyzer")

st.markdown("Enter a product/search term. The app will fetch up to 5 reviews per star (5→1) and run sentiment analysis.")

query = st.text_input("Product or keywords", value="", placeholder="e.g. minimal face wash")

col1, col2 = st.columns([3,1])
with col2:
    max_per_star = st.number_input("Reviews per star", min_value=1, max_value=10, value=5, step=1)
    max_pages = st.number_input("Max pages to scan", min_value=1, max_value=20, value=8, step=1)
    run = st.button("Analyze")

if run and query.strip():
    with st.spinner("Searching & scraping (fast requests)..."):
        result, link = scrape_product_reviews(query, max_per_star=max_per_star, max_pages=int(max_pages))

    if "error" in result:
        st.error(result["error"])
    else:
        st.success(f"Product: {result['title']}")
        st.write(f"ASIN: {result['asin']}")
        if link:
            st.write("Product URL:", link)

        reviews = result["reviews"]
        # Build combined dataframe for charts
        records = []
        for star in [5,4,3,2,1]:
            for r in reviews.get(star, []):
                records.append({
                    "star": star,
                    "rating": r["rating"],
                    "text": r["text"],
                    "sentiment": r["sentiment"],
                    "polarity": r["polarity"]
                })
        if records:
            df = pd.DataFrame(records)
            st.markdown("### Sentiment counts")
            counts = df["sentiment"].value_counts().reindex(["Positive","Neutral","Negative"]).fillna(0).astype(int)
            cdf = counts.reset_index()
            cdf.columns = ["sentiment","count"]
            chart = alt.Chart(cdf).mark_bar().encode(
                x=alt.X("sentiment:N"),
                y=alt.Y("count:Q"),
                color="sentiment:N"
            )
            st.altair_chart(chart, use_container_width=True)

            st.markdown("### Reviews by star")
            for star in [5,4,3,2,1]:
                st.subheader(f"{star}-Star Reviews")
                star_rows = df[df["star"] == star]
                if star_rows.empty:
                    st.info("No reviews found for this star rating.")
                else:
                    for _, row in star_rows.iterrows():
                        st.write(f"- [{row['sentiment']}] {row['text']}")
            st.download_button("Download CSV", data=open(result["csv"], "rb").read(),
                               file_name=result["csv"], mime="text/csv")
        else:
            st.info("No reviews were scraped (maybe Amazon changed layout or product has no reviews).")
else:
    st.info("Enter a product name and press Analyze.")
