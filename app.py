import os
import csv
import io
from flask import Flask, render_template, request, redirect, send_file, session
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "default_secret_key")  # Should be set in Heroku config

def transform_list(input_list):
    return [item.lower().replace(" ", "-") for item in input_list]

def get_price(items):
    chrome_options = Options()
    chrome_options.binary_location = os.environ.get("GOOGLE_CHROME_BIN", "/usr/bin/google-chrome")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(
        executable_path=os.environ.get("CHROMEDRIVER_PATH", "/usr/bin/chromedriver"),
        options=chrome_options
    )

    total = 0
    results = []

    for item in items:
        url = f"https://www.ge-tracker.com/item/{item}"
        driver.get(url)

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "has-tooltip"))
            )

            soup = BeautifulSoup(driver.page_source, "html.parser")
            tooltip_spans = soup.find_all("span", class_="has-tooltip")

            if tooltip_spans:
                price_text = tooltip_spans[0].text.strip()
                numeric_price = int(price_text.replace(",", ""))
                results.append((item.replace("-", " ").title(), price_text))
                total += numeric_price
            else:
                results.append((item.replace("-", " ").title(), "Not found"))
        except Exception:
            results.append((item.replace("-", " ").title(), "Error"))
    
    driver.quit()
    return results, total

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        items_raw = request.form.get("items")
        item_list = [line.strip() for line in items_raw.splitlines() if line.strip()]
        formatted_list = transform_list(item_list)
        results, total = get_price(formatted_list)
        total_millions = f"{total / 1_000_000:.2f}M"

        # Store in Flask session
        session["results"] = results
        session["total"] = total
        return render_template("results.html", results=results, total=total_millions)

    return render_template("index.html")

@app.route("/download")
def download_csv():
    results = session.get("results", [])
    total = session.get("total", 0)

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Item", "Price"])
    for row in results:
        cw.writerow(row)
    cw.writerow([])
    cw.writerow(["Total", f"{total:,}"])
    output = io.BytesIO()
    output.write(si.getvalue().encode("utf-8"))
    output.seek(0)
    return send_file(output, mimetype="text/csv", download_name="prices.csv", as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
