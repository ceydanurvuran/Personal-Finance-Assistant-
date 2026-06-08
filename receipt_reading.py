import os
import re

import cv2
import numpy as np
from PIL import Image, ImageOps
from paddleocr import PaddleOCR

# Disable accelerator warnings/errors
os.environ["FLAGS_enable_pir_api"] = "0"
print("OCR engine ready.")
ocr = None


def get_ocr():
    global ocr

    if ocr is None:
        print("OCR loading...")
        ocr = PaddleOCR(
            use_textline_orientation=False,
            lang="tr",
            enable_mkldnn=False
        )

    return ocr


def normalize_text(text):
    return (
        str(text).upper()
        .replace("Ş", "S")
        .replace("İ", "I")
        .replace("İ", "I")
        .replace("Ç", "C")
        .replace("Ğ", "G")
        .replace("Ü", "U")
        .replace("Ö", "O")
    )


def parse_price(price_str):
    clean_str = normalize_text(price_str)
    clean_str = clean_str.replace("TL", "").replace("TRY", "").replace("*", "").replace("%", "")
    clean_str = re.sub(r"[^0-9,.]", "", clean_str).strip()

    if "." in clean_str and "," in clean_str:
        clean_str = clean_str.replace(".", "").replace(",", ".")
    elif "," in clean_str:
        clean_str = clean_str.replace(",", ".")

    try:
        return float(clean_str)
    except ValueError:
        return 0.0


def load_image(image_source):
    if not isinstance(image_source, str):
        return image_source

    if image_source.lower().endswith(".pdf"):
        return None

    try:
        pil_img = Image.open(image_source)
        pil_img = ImageOps.exif_transpose(pil_img).convert("RGB")
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    except Exception:
        return cv2.imread(image_source)


def prepare_ocr_images(img):
    h, w = img.shape[:2]
    max_size = 1400
    min_size = 900
    prepared = [img]

    if max(h, w) > max_size:
        ratio = max_size / max(h, w)
        img = cv2.resize(img, (int(w * ratio), int(h * ratio)), interpolation=cv2.INTER_AREA)
        prepared[0] = img
    elif max(h, w) < min_size:
        ratio = min_size / max(h, w)
        img = cv2.resize(img, (int(w * ratio), int(h * ratio)), interpolation=cv2.INTER_CUBIC)
        prepared[0] = img

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 45, 45)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 11
    )
    prepared.append(cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR))
    return prepared


def extract_text_lines(result):
    lines = []

    def walk(node):
        if node is None:
            return
        if isinstance(node, dict):
            if isinstance(node.get("rec_texts"), list):
                lines.extend(str(t) for t in node["rec_texts"] if str(t).strip())
            for value in node.values():
                walk(value)
            return
        if isinstance(node, (list, tuple)):
            if len(node) >= 2 and isinstance(node[1], (list, tuple)) and node[1] and isinstance(node[1][0], str):
                lines.append(node[1][0])
                return
            for item in node:
                walk(item)

    walk(result)

    cleaned = []
    for line in lines:
        line = str(line).strip()
        if line and line not in cleaned:
            cleaned.append(line)
    return cleaned


def guess_store_and_category(text_lines):
    clean_text = normalize_text(" ".join(text_lines)).replace(" ", "")
    store_name = "Unknown Store"
    category = "Other"

    if "MIGROS" in clean_text:
        store_name = "Migros"
        category = "Supermarket"
    elif any(keyword in clean_text for keyword in ["A101", "AIOI", "A1O1"]):
        store_name = "A101"
        category = "Supermarket"
    elif any(keyword in clean_text for keyword in ["BIM", "B1M"]):
        store_name = "BIM"
        category = "Supermarket"
    elif "SOK" in clean_text:
        store_name = "Sok Market"
        category = "Supermarket"
    elif any(keyword in clean_text for keyword in ["CARREFOUR", "FILEMARKET", "MACROCENTER"]):
        store_name = "Market"
        category = "Supermarket"
    elif any(keyword in clean_text for keyword in ["BURGER", "KING", "BURGERKING"]):
        store_name = "Burger King"
        category = "Restaurant / Fast Food"
    elif any(keyword in clean_text for keyword in ["STARBUCKS", "MCDONALD", "KFC", "DOMINOS", "PIZZA"]):
        store_name = "Restaurant"
        category = "Restaurant / Fast Food"
    elif any(keyword in clean_text for keyword in ["JACK", "JONES"]):
        store_name = "Jack & Jones"
        category = "Clothing"
    elif "KOTON" in clean_text:
        store_name = "Koton"
        category = "Clothing"
    elif any(keyword in clean_text for keyword in ["LCW", "WAIKIKI", "LCWAIKIKI"]):
        store_name = "LC Waikiki"
        category = "Clothing"
    elif "ZARA" in clean_text:
        store_name = "Zara"
        category = "Clothing"

    if store_name == "Unknown Store":
        ignored = ["FIS", "TARIH", "SAAT", "KDV", "TOPLAM", "KASIYER", "VERGI", "MERSIS"]
        for line in text_lines[:8]:
            simple = normalize_text(line)
            if len(simple) > 3 and not any(word in simple for word in ignored) and not re.search(r"\d+[,.]\d{2}", simple):
                store_name = line.strip()[:40]
                break

    return store_name, category


def find_total_amount(text_lines):
    total_words = ["GENEL TOPLAM", "TOPLAM", "ODENECEK", "ÖDENECEK", "TUTAR", "NAKIT", "NAKİT", "KREDI", "KREDİ"]
    exclude_words = ["ARA TOPLAM", "KDV TOPLAM", "KDV", "PARA USTU", "PARA ÜSTÜ"]

    for i, raw_line in enumerate(text_lines):
        line_upper = normalize_text(raw_line)
        compact = line_upper.replace(" ", "")
        has_total_word = any(normalize_text(word).replace(" ", "") in compact for word in total_words)
        has_excluded_word = any(normalize_text(word).replace(" ", "") in compact for word in exclude_words)

        if has_total_word and not has_excluded_word:
            matches = re.findall(r"\d+[.,\d]*[.,]\d{2}", line_upper)
            if matches:
                return parse_price(matches[-1])

            for j in range(i + 1, min(len(text_lines), i + 4)):
                next_matches = re.findall(r"\d+[.,\d]*[.,]\d{2}", text_lines[j].replace(" ", ""))
                if next_matches:
                    return parse_price(next_matches[-1])

    found_prices = []
    for raw_line in text_lines:
        line = normalize_text(raw_line).replace(" ", "").replace("TL", "").replace("*", "").replace("%", "")
        matches = re.findall(r"\d+[.,\d]*[.,]\d{2}", line)
        for match in matches:
            price_val = parse_price(match)
            if 0.0 < price_val < 200000.0:
                found_prices.append(price_val)

    return max(found_prices) if found_prices else 0.0


def process_receipt(image_source):
    img = load_image(image_source)

    if img is None:
        if isinstance(image_source, str) and image_source.lower().endswith(".pdf"):
            return "PDF Receipt", 0.0, "Unsupported PDF"
        return "Unreadable", 0.0, "Corrupted Image"

    try:
        ocr_engine = get_ocr()
        text_lines = []
        for prepared_img in prepare_ocr_images(img):
            result = ocr_engine.ocr(prepared_img)
            text_lines.extend(extract_text_lines(result))
        text_lines = list(dict.fromkeys(line for line in text_lines if line.strip()))
    except Exception as e:
        print("Receipt OCR error:", e)
        return "Unreadable", 0.0, "OCR Error"

    if not text_lines:
        return "Unreadable", 0.0, "No Text Found"

    store_name, category = guess_store_and_category(text_lines)
    amount = find_total_amount(text_lines)

    return store_name, amount, category
