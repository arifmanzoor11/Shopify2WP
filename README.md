# 🛒 Shopify to WordPress CSV Converter

A simple Flask web app that converts Shopify product data (`.json` or public URL) into a WooCommerce-compatible CSV file for bulk import.

---

## 🚀 Features

- Upload Shopify `.json` export or fetch from Shopify URL
- Handles simple and variable products
- Auto-generates SKUs if missing
- Fixes attribute names (e.g., "Colour" → "Color")
- Fully WooCommerce-compatible CSV
- Built with Flask + Bootstrap

---

## 🧪 Demo

```bash
git clone https://github.com/yourusername/shopify-to-wordpress-csv.git
cd shopify-to-wordpress-csv
pip install -r requirements.txt
python app.py
