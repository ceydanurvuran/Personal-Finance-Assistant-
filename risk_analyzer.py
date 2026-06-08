import sqlite3
import pandas as pd

def analyze_risk(db_path="finance.db"):
    # Veritabanına bağlanıp işlemleri Pandas DataFrame'e alıyoruz
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM transactions", conn)
    conn.close()

    if df.empty:
        return ["Henüz yeterli işlem verisi yok."]

    risk_alerts = []

    # 1. Gelir - Gider %80 Kuralı
    import sqlite3
import pandas as pd

def analyze_risk(db_path="finance.db", user_id=None):
    conn = sqlite3.connect(db_path)
    if user_id is None:
        df = pd.read_sql_query("SELECT * FROM transactions", conn)
    else:
        df = pd.read_sql_query("SELECT * FROM transactions WHERE user_id=?", conn, params=(user_id,))
    conn.close()

    if df.empty:
        return ["Not enough transaction data yet."]

    risk_alerts = []

    # 1. Income - Expense 80% Rule
    total_income = df[df['type'] == 'income']['amount'].sum()
    total_expense = df[df['type'] == 'expense']['amount'].sum()

    if total_income > 0:
        expense_ratio = (total_expense / total_income) * 100
        if expense_ratio > 80:
            risk_alerts.append(f"⚠️ HIGH RISK: Your expenses have reached {expense_ratio:.1f}% of your income! Red line crossed.")
    elif total_income == 0 and total_expense > 0:
        # 0'a bölme açığını kapatan İngilizce uyarı
        risk_alerts.append("⚠️ HIGH RISK: You are spending without any recorded income! Balance is dropping directly into negative.")

    # 2. Recurring Expenses Check
    expenses_df = df[df['type'] == 'expense']
    recurring = expenses_df.groupby('description').size()
    subscriptions = recurring[recurring > 1]
    
    if not subscriptions.empty:
        risk_alerts.append("🔄 Recurring Expenses (Possible subscription, please check):")
        for name, count in subscriptions.items():
            risk_alerts.append(f" - '{name}' has been charged {count} times.")

    if not risk_alerts:
        risk_alerts.append("✅ Great! No critical financial risks detected at the moment.")

    return risk_alerts
    
    # 1'den fazla kez yapılan harcamaları yakalıyoruz
    subscriptions = recurring[recurring > 1]
    
    if not subscriptions.empty:
        risk_alerts.append("🔄 Tekrar Eden Harcamalar (Abonelik olabilir, kontrol edin):")
        for name, count in subscriptions.items():
            risk_alerts.append(f" - '{name}' adlı harcama {count} kez yapılmış.")

    if not risk_alerts:
        risk_alerts.append("✅ Harika! Şu an için kritik bir finansal risk görünmüyor.")

    return risk_alerts

# Test çalıştırması
if __name__ == "__main__":
    uyarilar = analyze_risk()
    for uyari in uyarilar:
        print(uyari)
