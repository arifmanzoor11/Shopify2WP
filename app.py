from flask import Flask, request, render_template, send_file
import pandas as pd
import requests
import os
import io
import json
import logging
from urllib.parse import urlparse
from werkzeug.utils import secure_filename

# Constants
GRAMS_TO_POUNDS = 453.592
ALLOWED_EXTENSIONS = {"json"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_url(url):
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return None
        if not url.endswith("/products.json"):
            url = url.rstrip("/") + "/products.json"
        return url
    except:
        return None

def get_image(product, variant=None):
    if variant and variant.get("featured_image") and variant["featured_image"].get("src"):
        return variant["featured_image"]["src"]
    return product.get("images", [{}])[0].get("src", "")

def get_option_values(product, variants):
    options = {}
    for i in range(3):  # Shopify supports up to 3
        if i < len(product.get("options", [])):
            name = product["options"][i].get("name", "").replace("Colour", "Color")
            values = {v.get(f"option{i+1}") for v in variants if v.get(f"option{i+1}") and v.get(f"option{i+1}") != "Default Title"}
            if values:
                options[name] = sorted(values)
    return options

def build_row(base=None, overrides=None):
    defaults = {
        "ID": "", "Type": "", "SKU": "", "Name": "", "Published": 1,
        "Is featured?": 0, "Visibility in catalog": "visible", "Short description": "",
        "Description": "", "Date sale price starts": "", "Date sale price ends": "",
        "Tax status": "taxable", "Tax class": "", "In stock?": "", "Stock": "",
        "Backorders allowed?": 0, "Sold individually?": 0, "Weight (lbs)": "",
        "Length (in)": "", "Width (in)": "", "Height (in)": "", "Allow customer reviews?": 1,
        "Purchase note": "", "Sale price": "", "Regular price": "", "Categories": "",
        "Tags": "", "Shipping class": "", "Images": "", "Download limit": "",
        "Download expiry days": "", "Parent": "", "Grouped products": "", "Upsells": "",
        "Cross-sells": "", "External URL": "", "Button text": "", "Position": "",
        "Attribute 1 name": "", "Attribute 1 value(s)": "", "Attribute 1 visible": "",
        "Attribute 1 global": "", "Attribute 2 name": "", "Attribute 2 value(s)": "",
        "Attribute 2 visible": "", "Attribute 2 global": "", "Meta: _wpcom_is_markdown": 1,
        "Download 1 name": "", "Download 1 URL": "", "Download 2 name": "", "Download 2 URL": ""
    }
    row = defaults.copy()
    if base:
        row.update(base)
    if overrides:
        row.update(overrides)
    return row

def create_parent_row(product, options, sku):
    title = product.get("title", "")
    images = ", ".join([get_image(product, v) for v in product.get("variants", []) if get_image(product, v)])
    return build_row({
        "Type": "variable",
        "SKU": sku,
        "Name": title,
        "Published": 1 if product.get("published_at") else 0,
        "Description": product.get("body_html", ""),
        "Categories": product.get("product_type", ""),
        "Tags": ", ".join(product.get("tags", [])),
        "Images": images,
        "In stock?": 1,
        "Attribute 1 name": list(options)[0] if options else "",
        "Attribute 1 value(s)": ", ".join(options.get(list(options)[0], [])) if options else "",
        "Attribute 1 visible": 1,
        "Attribute 1 global": 1,
        "Attribute 2 name": list(options)[1] if len(options) > 1 else "",
        "Attribute 2 value(s)": ", ".join(options.get(list(options)[1], [])) if len(options) > 1 else "",
        "Attribute 2 visible": 1 if len(options) > 1 else "",
        "Attribute 2 global": 0 if len(options) > 1 else ""
    })

def create_variation_row(product, variant, options, index, parent_sku):
    title = product.get("title", "")
    option_parts = [variant.get(f"option{i+1}") for i in range(3) if variant.get(f"option{i+1}") and variant.get(f"option{i+1}") != "Default Title"]
    return build_row({
        "Type": "variation",
        "SKU": variant.get("sku") or f"{parent_sku}-{index}",
        "Name": f"{title} - {', '.join(option_parts)}",
        "Published": 1 if product.get("published_at") else 0,
        "Sale price": str(variant.get("price", "")),
        "Regular price": str(variant.get("compare_at_price") or variant.get("price", "")),
        "In stock?": 1 if variant.get("available", True) else 0,
        "Stock": str(variant.get("inventory_quantity", "")),
        "Weight (lbs)": round(variant.get("grams", 0) / GRAMS_TO_POUNDS, 2) if variant.get("grams") else "",
        "Images": get_image(product, variant),
        "Parent": parent_sku,
        "Position": index,
        "Attribute 1 name": list(options)[0] if options else "",
        "Attribute 1 value(s)": variant.get("option1", ""),
        "Attribute 1 global": 1,
        "Attribute 2 name": list(options)[1] if len(options) > 1 else "",
        "Attribute 2 value(s)": variant.get("option2", ""),
        "Attribute 2 global": 0 if len(options) > 1 else ""
    })

def create_simple_row(product, variant):
    title = product.get("title", "")
    sku = variant.get("sku", f"{secure_filename(title.lower().replace(' ', '-'))}-simple")
    return build_row({
        "Type": "simple",
        "SKU": sku,
        "Name": title,
        "Published": 1 if product.get("published_at") else 0,
        "Description": product.get("body_html", ""),
        "Categories": product.get("product_type", ""),
        "Tags": ", ".join(product.get("tags", [])),
        "Images": get_image(product, variant),
        "Sale price": str(variant.get("price", "")),
        "Regular price": str(variant.get("compare_at_price") or variant.get("price", "")),
        "In stock?": 1 if variant.get("available", True) else 0,
        "Stock": str(variant.get("inventory_quantity", "")),
        "Weight (lbs)": round(variant.get("grams", 0) / GRAMS_TO_POUNDS, 2) if variant.get("grams") else "",
        "Attribute 1 name": product.get("options", [{}])[0].get("name", "").replace("Colour", "Color"),
        "Attribute 1 value(s)": variant.get("option1", ""),
        "Attribute 1 visible": 1,
        "Attribute 1 global": 1
    })

def convert_to_wordpress_csv(products):
    rows = []
    for product in products:
        variants = product.get("variants", [])
        options = get_option_values(product, variants)
        title = product.get("title", "")
        slug = secure_filename(title.lower().replace(" ", "-"))
        parent_sku = product.get("variants", [{}])[0].get("sku")
        if not parent_sku:
            parent_sku = f"{slug}"

        if len(variants) > 1 and options:
            rows.append(create_parent_row(product, options, parent_sku))
            for i, variant in enumerate(variants, start=1):
                if variant.get("option1") == "Default Title":
                    continue
                rows.append(create_variation_row(product, variant, options, i, parent_sku))
        else:
            variant = variants[0] if variants else {}
            rows.append(create_simple_row(product, variant))

    df = pd.DataFrame(rows)
    output = io.BytesIO()
    df.to_csv(output, index=False, encoding="utf-8-sig")
    output.seek(0)
    return output

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            json_data = None
            if "json_file" in request.files and request.files["json_file"].filename:
                uploaded_file = request.files["json_file"]
                if not allowed_file(uploaded_file.filename):
                    return render_template("index.html", error="Invalid file type. Upload a JSON file.")
                json_data = json.load(uploaded_file)
            elif request.form.get("shopify_url"):
                url = validate_url(request.form.get("shopify_url"))
                if not url:
                    return render_template("index.html", error="Invalid Shopify URL.")
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                json_data = response.json()
            else:
                return render_template("index.html", error="Provide a JSON file or Shopify URL.")

            products = json_data.get("products", [])
            if not products:
                return render_template("index.html", error="No products found.")

            csv_file = convert_to_wordpress_csv(products)
            return send_file(csv_file, mimetype="text/csv", as_attachment=True, download_name="wordpress_import.csv")

        except Exception as e:
            logger.error(f"Error: {e}")
            return render_template("index.html", error="Something went wrong. Please try again.")

    return render_template("index.html")

@app.route("/documentation")
def documentation():
    return render_template("documentation.html")

# Register error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

if __name__ == "__main__":
      app.run(debug=True, port=3004)
