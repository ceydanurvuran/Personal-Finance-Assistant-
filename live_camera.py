import cv2
import requests
import os

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "test1"   # BURAYI KENDİ BİLGİLERİNLE DEĞİŞTİR
PASSWORD = "1234"           # BURAYI KENDİ BİLGİLERİNLE DEĞİŞTİR
# ---------------

def login_and_get_token():
    print(f"🔄 '{USERNAME}' hesabı ile sunucuya bağlanılıyor...")
    try:
        response = requests.post(f"{BASE_URL}/login", json={"username": USERNAME, "password": PASSWORD})
        if response.status_code == 200:
            print("✅ Giriş Başarılı! Token alındı.")
            return response.json()["access_token"]
        else:
            print("❌ Giriş başarısız! Kullanıcı adı veya şifre yanlış olabilir.")
            return None
    except requests.exceptions.ConnectionError:
        print("❌ Sunucuya ulaşılamıyor! 'uvicorn main:app --reload' komutunun çalıştığından emin ol.")
        return None

def capture_and_send():
    # 1. Önce token'ı al
    token = login_and_get_token()
    if not token:
        return

    # 2. Kamerayı başlat
    cap = cv2.VideoCapture(0) # Eğer 0'da açılmazsa 1, 2 diye deneyebilirsin
    if not cap.isOpened():
        print("❌ Kamera açılamadı!")
        return

    print("\n" + "="*40)
    print("📸 KAMERA AÇILDI!")
    print("👉 Fişi kameraya göster ve 'SPACE' (BOŞLUK) tuşuna bas.")
    print("👉 Çıkmak için 'ESC' tuşuna bas.")
    print("="*40 + "\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        cv2.imshow('Fis Tarayici', frame)
        key = cv2.waitKey(1)

        # SPACE (Boşluk) tuşuna basıldıysa fotoğraf çek
        if key == 32: 
            print("📸 Fotoğraf çekildi! Yapay Zeka'ya gönderiliyor, lütfen bekle...")
            
            # Geçici olarak fotoğrafı kaydet
            temp_filename = "temp_receipt.jpg"
            cv2.imwrite(temp_filename, frame)

            # API'ye Gönder
            headers = {"Authorization": f"Bearer {token}"}
            with open(temp_filename, "rb") as f:
                files = {"file": (temp_filename, f, "image/jpeg")}
                res = requests.post(f"{BASE_URL}/upload-receipt", headers=headers, files=files)

            # Sonucu Ekrana Yazdır
            if res.status_code == 200:
                data = res.json()
                print("\n✅ BİNGO! FİŞ BAŞARIYLA İŞLENDİ:")
                print(f"🏢 Mağaza : {data.get('ai_results', {}).get('store')}")
                print(f"💰 Tutar  : {data.get('ai_results', {}).get('total')} TL")
                print(f"🏷️ Kategori: {data.get('ai_results', {}).get('category')}\n")
            else:
                print(f"\n❌ HATA OLUŞTU: {res.text}\n")

            # İşlem bitince geçici dosyayı sil
            if os.path.exists(temp_filename):
                os.remove(temp_filename)

        # ESC tuşuna basıldıysa çık
        elif key == 27: 
            print("Kapatılıyor...")
            break

    # Temizlik
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    capture_and_send()
