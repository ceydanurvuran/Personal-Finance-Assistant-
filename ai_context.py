from fastapi import APIRouter, Depends, HTTPException
from core import get_connection, verify_token
from currency_service import get_rates
from forecaster import predict_next_week_expense

# Yapay zeka motorumuzu backend'e çağırıyoruz
from ai_engine import get_ai_financial_advice

router = APIRouter()


# -------------------------
# NET WORTH
# -------------------------
def net_worth(cursor, user_id):
    cursor.execute("""
        SELECT type, SUM(amount) as total
        FROM transactions
        WHERE user_id=?
        GROUP BY type
    """, (user_id,))

    rows = cursor.fetchall()

    income = 0
    expense = 0

    for r in rows:
        if r["type"] == "income":
            income += r["total"] or 0
        elif r["type"] == "expense":
            expense += r["total"] or 0

    return income, expense, income - expense


# -------------------------
# WEEKLY DATA
# -------------------------
def weekly(cursor, user_id):
    cursor.execute("""
        SELECT date(date) as day, type, SUM(amount) as total
        FROM transactions
        WHERE user_id=?
        AND date >= date('now','-7 days')
        GROUP BY day, type
    """, (user_id,))

    return cursor.fetchall()


# -------------------------
# RECENT TRANSACTIONS
# -------------------------
def recent(cursor, user_id):
    cursor.execute("""
        SELECT type, description, amount, category, date
        FROM transactions
        WHERE user_id=?
        ORDER BY date DESC
        LIMIT 20
    """, (user_id,))

    return [dict(i) for i in cursor.fetchall()]


# -------------------------
# WEEKLY NET CALC
# -------------------------
def calculate_weekly_net(weekly_rows):
    income = 0
    expense = 0
    for r in weekly_rows:
        if r["type"] == "income":
            income += r["total"] or 0
        elif r["type"] == "expense":
            expense += r["total"] or 0
    return max(0, income - expense)


# -------------------------
# MAIN AI CONTEXT ENDPOINT
# -------------------------
@router.get("/ai/context")
def ai_context(
    target_amount: float = None,
    target_currency: str = None,
    user=Depends(verify_token)
):

    rates = get_rates()

    if not rates or not all(rates.get(code, 0) > 0 for code in ("usd", "eur", "gbp")):
        raise HTTPException(
            status_code=503,
            detail="Currency rates service unavailable"
        )

    conn = get_connection()

    try:
        cursor = conn.cursor()
        uid = user["user_id"]

        # Parametreler verilmediyse veritabanından oku
        if target_amount is None or target_currency is None:
            cursor.execute("SELECT target_amount, target_currency FROM users WHERE id=?", (uid,))
            db_goal = cursor.fetchone()
            if db_goal:
                if target_amount is None:
                    target_amount = db_goal["target_amount"] if db_goal["target_amount"] is not None else 100.0
                if target_currency is None:
                    target_currency = db_goal["target_currency"] if db_goal["target_currency"] is not None else "USD"
            else:
                if target_amount is None: target_amount = 100.0
                if target_currency is None: target_currency = "USD"
        else:
            # Parametreler girildiyse veritabanına kaydet
            cursor.execute("""
                UPDATE users
                SET target_amount=?, target_currency=?
                WHERE id=?
            """, (target_amount, target_currency.upper(), uid))
            conn.commit()

        inc, exp, net = net_worth(cursor, uid)

        weekly_rows = weekly(cursor, uid)
        weekly_net = calculate_weekly_net(weekly_rows)

        # Haftalık veriyi AI motoru ve UI sözlük yapısına dönüştür
        weekly_data = {}
        for r in weekly_rows:
            day = r["day"]
            t = r["type"]
            if day not in weekly_data:
                weekly_data[day] = {"income": 0, "expense": 0}
            weekly_data[day][t] += r["total"] or 0

        # -------------------------
        # REAL FX RATE ENGINE (1 Yabancı Para = Kaç TL?)
        # -------------------------
        usdtry = 1 / rates["usd"] if rates["usd"] > 0 else 0
        eurtry = 1 / rates["eur"] if rates["eur"] > 0 else 0
        gbptry = 1 / rates["gbp"] if rates["gbp"] > 0 else 0

        currency_key = target_currency.lower()

        # ✔ Backend converts to TRY (Seçilen birime göre TL karşılığı tam hesaplanır)
        if currency_key == "try":
            goal_try = target_amount
        elif currency_key == "usd":
            goal_try = target_amount * usdtry
        elif currency_key == "eur":
            goal_try = target_amount * eurtry
        elif currency_key == "gbp":
            goal_try = target_amount * gbptry
        else:
            goal_try = target_amount

        # -------------------------
        # TIME ESTIMATION (✔ Weeks needed computed)
        # -------------------------
        weeks_needed = (
            round(goal_try / weekly_net, 1)
            if weekly_net > 0 else None
        )

        # -------------------------
        # FINANCE OBJECT
        # -------------------------
        finance = {
            "income": inc,
            "expense": exp,
            "net_try": net,

            # FX
            "net_usd": round(net * rates["usd"], 2),
            "net_eur": round(net * rates["eur"], 2),
            "net_gbp": round(net * rates["gbp"], 2),

            # Crypto
            "net_btc": round(net / rates["btc"], 8) if rates["btc"] > 0 else 0,
            "net_eth": round(net / rates["eth"], 8) if rates["eth"] > 0 else 0,

            # Weekly analysis (✔ Weekly savings calculated)
            "weekly_saving_avg_try": round(weekly_net, 2),

            # Goal system
            "goal": {
                "selected_amount": target_amount,
                "selected_currency": currency_key.upper(),
                "target_try": round(goal_try, 2),
                "weeks_needed": weeks_needed
            },

            # Progress
            "progress_percent": round((net / goal_try) * 100, 2) if goal_try > 0 else 0
        }

        recent_txs = recent(cursor, uid)

        # 🔮 GELECEK TAHMİNİ MOTORUNU ÇALIŞTIR
        forecast_data = predict_next_week_expense(user_id=uid)

        # 🧠 YAPAY ZEKA MOTORUNA ARTIK TAHMİNLERİ DE YOLLUYORUZ
        ai_advice = get_ai_financial_advice(finance, weekly_data, recent_txs, forecast_data, rates)

        return {
            "finance": finance,
            "rates": {
                "usd": rates["usd"], "eur": rates["eur"], "gbp": rates["gbp"],
                "btc": rates["btc"], "eth": rates["eth"],
                "usdtry": round(usdtry, 2), "eurtry": round(eurtry, 2), "gbptry": round(gbptry, 2),
                "source": rates.get("source", "Unknown"),
                "crypto_source": rates.get("crypto_source", "Unknown"),
                "rate_date": rates.get("rate_date"),
                "fetched_at": rates.get("fetched_at"),
                "is_live": rates.get("is_live", False)
            },
            "weekly": weekly_data,
            "recent": recent_txs,
            "forecast": forecast_data,
            "ai_advice": ai_advice 
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )

    finally:
        conn.close()
