import sqlite3
from datetime import datetime, timedelta

def add_past_transactions(db_path="finance.db", user_id=1):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print("⏳ Geçmişe dönük veriler ekleniyor...")

    # Son 4 gün için her güne birer harcama ekliyoruz
    for i in range(1, 5):
        # Bugünden i gün öncesini hesapla
        past_date = datetime.now() - timedelta(days=i)
        formatted_date = past_date.strftime("%Y-%m-%d %H:%M:%S")
        
        # Giderek artan sahte harcamalar (150, 300, 450, 600 TL)
        amount = 150.0 * i 
        
        cur.execute("""
            INSERT INTO transactions (user_id, type, description, amount, category, date)
            VALUES (?, 'expense', ?, ?, 'Food', ?)
        """, (user_id, f"Past Test Expense Day {i}", amount, formatted_date))

    conn.commit()
    conn.close()
    print("✅ İşlem tamam! 4 günlük geçmiş veri veritabanına işlendi.")

if __name__ == "__main__":
    add_past_transactions()