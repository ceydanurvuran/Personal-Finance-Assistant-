import os
import re
import cv2
import numpy as np
from paddleocr import PaddleOCR

# Disable accelerator warnings/errors
os.environ["FLAGS_enable_pir_api"] = "0"
print("🧠 PaddleOCR Motoru Yükleniyor... Lütfen Bekleyin.")
ocr = None

def get_ocr():
    global ocr

    if ocr is None:
        print("🧠 OCR loading...")
        ocr = PaddleOCR(
            use_textline_orientation=False,
            lang='tr',
            enable_mkldnn=False
        )

    return ocr

def parse_price(price_str):
    clean_str = price_str.replace('TL', '').replace('*', '').replace('%', '').strip()
    if '.' in clean_str and ',' in clean_str:
        clean_str = clean_str.replace('.', '').replace(',', '.')
    elif ',' in clean_str:
        clean_str = clean_str.replace(',', '.')
    try:
        return float(clean_str)
    except ValueError:
        return 0.0

def process_receipt(image_source):
    if isinstance(image_source, str):
        img = cv2.imread(image_source)
    else:
        img = image_source

    if img is None:
        return "Unreadable", 0.0, "Corrupted Image"
        
    h, w = img.shape[:2]
    max_size = 800 
    
    if max(h, w) > max_size:
        ratio = max_size / max(h, w)
        img = cv2.resize(img, (int(w * ratio), int(h * ratio)))

    try:
       ocr_engine = get_ocr()
       result = ocr_engine.ocr(img)
    except Exception:
        return "Unreadable", 0.0, "Error"
    
    text_lines = []
    try:
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

    raw_text = " ".join(text_lines).upper()
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
    elif any(keyword in clean_text for keyword in ["JACK", "JONES"]):
        store_name = "JACK & JONES"
        category = "Clothing"
    elif any(keyword in clean_text for keyword in ["KOTON"]):
        store_name = "KOTON"
        category = "Clothing"
    elif any(keyword in clean_text for keyword in ["LCW", "WAIKIKI", "LCWAIKIKI"]):
        store_name = "LC WAIKIKI"
        category = "Clothing"
    elif any(keyword in clean_text for keyword in ["ZARA"]):
        store_name = "ZARA"
        category = "Clothing"

    amount = 0.0

    for i, raw_line in enumerate(text_lines):
        line_upper = raw_line.upper().replace('Ş', 'S').replace('İ', 'I').replace(' ', '')
        if "TOPLAM" in line_upper and "ARA" not in line_upper and "KDV" not in line_upper:
            matches = re.findall(r'\d+[.,\d]*[.,]\d{2}', line_upper)
            if matches:
                amount = parse_price(matches[-1])
                break 
            
            found = False
            for j in range(i + 1, min(len(text_lines), i + 3)):
                next_line = text_lines[j].replace(' ', '')
                next_matches = re.findall(r'\d+[.,\d]*[.,]\d{2}', next_line)
                if next_matches:
                    amount = parse_price(next_matches[-1])
                    found = True
                    break 
            if found:
                break

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