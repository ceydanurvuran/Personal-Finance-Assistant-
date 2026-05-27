from fastapi import APIRouter, Depends, HTTPException
from core import get_connection, verify_token
from currency_service import get_rates

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

    rows = cursor.fetchall()

    result = {}

    for r in rows:
        day = r["day"]
        t = r["type"]

        if day not in result:
            result[day] = {"income": 0, "expense": 0}

        result[day][t] += r["total"] or 0

    return result


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
def calculate_weekly_net(weekly_data):
    income = sum(day["income"] for day in weekly_data.values())
    expense = sum(day["expense"] for day in weekly_data.values())
    return max(0, income - expense)


# -------------------------
# MAIN AI CONTEXT ENDPOINT
# -------------------------
@router.get("/ai/context")
def ai_context(
    target_amount: float = 100.0,
    target_currency: str = "USD",
    user=Depends(verify_token)
):

    rates = get_rates()

    if not rates or "usd" not in rates:
        raise HTTPException(
            status_code=503,
            detail="Currency rates service unavailable"
        )

    conn = get_connection()

    try:
        cursor = conn.cursor()
        uid = user["user_id"]

        inc, exp, net = net_worth(cursor, uid)

        weekly_data = weekly(cursor, uid)
        weekly_net = calculate_weekly_net(weekly_data)

        # -------------------------
        # GOAL ENGINE
        # -------------------------
        currency_key = target_currency.lower()

        if currency_key == "try":
            goal_try = target_amount

        elif currency_key in rates and rates[currency_key] > 0:
            # 1 TRY = X currency → currency → TRY
            goal_try = target_amount / rates[currency_key]

        else:
            goal_try = target_amount  # fallback safety

        # -------------------------
        # TIME ESTIMATION
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

            # Weekly analysis
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

        return {
            "finance": finance,
            "rates": rates,
            "weekly": weekly_data,
            "recent": recent(cursor, uid)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )

    finally:
        conn.close()