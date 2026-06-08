import sqlite3
import pandas as pd

def predict_next_week_expense(db_path="finance.db", user_id=None):
    conn = sqlite3.connect(db_path)
    
    query = """
        SELECT date(date) as day, SUM(amount) as daily_total
        FROM transactions
        WHERE type = 'expense' AND date >= date('now', '-30 days')
        {user_filter}
        GROUP BY day
        ORDER BY day ASC
    """.format(user_filter="AND user_id=?" if user_id is not None else "")
    params = (user_id,) if user_id is not None else None
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty or len(df) < 3:
        return {
            "status": "insufficient_data",
            "message": "Not enough data for forecasting. (Need at least 3 days of expenses)."
        }

    avg_daily_expense = df['daily_total'].mean()
    predicted_weekly_expense = avg_daily_expense * 7
    max_expense_day = df.loc[df['daily_total'].idxmax()]

    return {
        "status": "success",
        "predicted_7_days_expense": round(predicted_weekly_expense, 2),
        "max_expense_date": max_expense_day['day'],
        "max_expense_amount": round(max_expense_day['daily_total'], 2)
    }
