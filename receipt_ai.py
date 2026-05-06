import os
import re
import glob
import cv2
from paddleocr import PaddleOCR

# Disable accelerator warnings/errors
os.environ["FLAGS_enable_pir_api"] = "0"
ocr = PaddleOCR(use_textline_orientation=False, lang='tr', enable_mkldnn=False)

def parse_price(price_str):
    # Cleans the price string and converts it to a float value
    clean_str = price_str.replace('TL', '').replace('*', '').replace('%', '').strip()
    if '.' in clean_str and ',' in clean_str:
        clean_str = clean_str.replace('.', '').replace(',', '.')
    elif ',' in clean_str:
        clean_str = clean_str.replace(',', '.')
    try:
        return float(clean_str)
    except ValueError:
        return 0.0

def process_receipt(image_path):
    # Resize image for performance optimization
    img = cv2.imread(image_path)
    if img is None:
        return "Unreadable", 0.0, "Corrupted Image"
        
    h, w = img.shape[:2]
    max_size = 800 
    
    if max(h, w) > max_size:
        ratio = max_size / max(h, w)
        img = cv2.resize(img, (int(w * ratio), int(h * ratio)))

    try:
        result = ocr.ocr(img)
    except Exception:
        return "Unreadable", 0.0, "Error"
    
    text_lines = []
    try:
        # Extract text list based on PaddleOCR version differences
        if isinstance(result, dict) and 'rec_texts' in result:
            text_lines = result['rec_texts']
        elif isinstance(result, list) and isinstance(result[0], dict) and 'rec_texts' in result[0]:
            text_lines = result[0]['rec_texts']
        else:
            for r in result:
                if isinstance(r, dict) and 'rec_texts' in r:
                    text_lines = r['rec_texts']
                    break
            if not text_lines:
                text_lines = [line[1][0] for line in result[0] if line is not None]
    except Exception:
        return "Unreadable", 0.0, "Error"

    if not text_lines:
        return "Unreadable", 0.0, "Error"

    # --- 1. STORE IDENTIFICATION ---
    raw_text = " ".join(text_lines).upper()
    # Standardize Turkish characters for easier matching
    clean_text = raw_text.replace(" ", "").replace("Ş", "S").replace("İ", "I").replace("Ç", "C").replace("Ğ", "G").replace("Ü", "U").replace("Ö", "O")
    
    store_name = "Unknown Store"
    category = "Other"
    
    if any(keyword in clean_text for keyword in ["MIGROS", "MİGROS"]):
        store_name = "MİGROS TİCARET A.Ş."
        category = "Supermarket"
    elif any(keyword in clean_text for keyword in ["A101", "AIOI", "A1O1"]):
        store_name = "A101"
        category = "Supermarket"
    elif any(keyword in clean_text for keyword in ["BIM", "B1M"]):
        store_name = "BİM"
        category = "Supermarket"
    elif any(keyword in clean_text for keyword in ["BURGER", "KING", "BURGERKING"]):
        store_name = "BURGER KING"
        category = "Restaurant / Fast Food"
    elif any(keyword in clean_text for keyword in ["JACK", "JONES", "BESTSELLER"]):
        store_name = "JACK & JONES"
        category = "Clothing"
    elif any(keyword in clean_text for keyword in ["KOTON"]):
        store_name = "KOTON"
        category = "Clothing"
    elif any(keyword in clean_text for keyword in ["LCW", "WAIKIKI", "LCWAIKIKI"]):
        store_name = "LC WAIKIKI"
        category = "Clothing"
    elif any(keyword in clean_text for keyword in ["ZARA", "ITX"]):
        store_name = "ZARA"
        category = "Clothing"

    amount = 0.0

    # --- 2. EXACT MATCH "TOTAL" ALGORITHM ---
    for i, raw_line in enumerate(text_lines):
        line_upper = raw_line.upper().replace('Ş', 'S').replace('İ', 'I').replace(' ', '')
        
        # Looking for "TOPLAM" (Total) but ignoring "ARA TOPLAM" (Subtotal) or "KDV'LI TOPLAM" (Total with VAT)
        if "TOPLAM" in line_upper and "ARA" not in line_upper and "KDV" not in line_upper:
            
            # Case 1: Amount is on the same line as "TOPLAM"
            matches = re.findall(r'\d+[.,\d]*[.,]\d{2}', line_upper)
            if matches:
                amount = parse_price(matches[-1])
                break # Target acquired, exit loop to avoid "Cash" (Nakit) lines
            
            # Case 2: Amount is on the next line(s) below "TOPLAM"
            found = False
            for j in range(i + 1, min(len(text_lines), i + 3)):
                next_line = text_lines[j].replace(' ', '')
                next_matches = re.findall(r'\d+[.,\d]*[.,]\d{2}', next_line)
                if next_matches:
                    amount = parse_price(next_matches[-1])
                    found = True
                    break # Target acquired
            if found:
                break

    # Fallback (Safety Net): If "TOPLAM" is not found or unreadable, get the highest valid price
    if amount == 0.0:
        found_prices = []
        for raw_line in text_lines:
            line = raw_line.upper().replace(' ', '').replace('TL', '').replace('*', '').replace('%', '')
            matches = re.findall(r'\d+[.,\d]*[.,]\d{2}', line)
            for match in matches:
                price_val = parse_price(match)
                if 0.0 < price_val < 20000.0:
                    found_prices.append(price_val)
        if found_prices:
            amount = max(found_prices)

    return store_name, amount, category

# --- EXECUTION BLOCK ---
import glob
import requests

API_URL = "http://127.0.0.1:8000"

USERNAME = "kendi_username"
PASSWORD = "kendi_password"

print("\n🔍 LOGGING IN...\n")

login_response = requests.post(
    f"{API_URL}/login",
    json={
        "username": USERNAME,
        "password": PASSWORD
    }
)

if login_response.status_code != 200:
    print("❌ Login failed. Check username/password or backend server.")
else:
    token = login_response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}"
    }

    print("\n🔍 SCANNING ALL RECEIPTS IN THE DIRECTORY...\n")

    receipt_files = glob.glob("*.jpg") + glob.glob("*.jpeg") + glob.glob("*.png")

    if not receipt_files:
        print("🚨 ERROR: No receipt images found!")
    else:
        for file in receipt_files:
            store, total, cat = process_receipt(file)

            print(f"[{file}] -> {store} | {cat} | {total} TL")

            if total > 0:
                response = requests.post(
                    f"{API_URL}/transactions",
                    headers=headers,
                    json={
                        "type": "expense",
                        "description": store,
                        "amount": total,
                        "category": cat
                    }
                )

                if response.status_code == 200:
                    print("✅ Added to system")
                else:
                    print("❌ Could not add:", response.text)

    print("\n✅ PROCESS COMPLETED!")