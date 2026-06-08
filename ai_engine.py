import json

# YENİ EKLENEN: rates_data parametresi eklendi
def get_ai_financial_advice(finance_data, weekly_data, recent_transactions, forecast_data, rates_data):
    """
    Backend'den gelen verileri alır, prompt içine gömer ve AI'dan tavsiye döner.
    """
    
    finance_str = json.dumps(finance_data, ensure_ascii=False, indent=2)
    weekly_str = json.dumps(weekly_data, ensure_ascii=False, indent=2)
    recent_str = json.dumps(recent_transactions, ensure_ascii=False, indent=2)
    forecast_str = json.dumps(forecast_data, ensure_ascii=False, indent=2)
    rates_str = json.dumps(rates_data, ensure_ascii=False, indent=2) # Kurları JSON'a çevirdik
    
    # YENİ EKLENEN: Prompt içine "LIVE FX & CRYPTO RATES" eklendi ve ACTION kısmı güncellendi
    system_prompt = f"""
    You are a direct, expert AI financial advisor. Analyze the data below and provide a VERY CONCISE, clear, and actionable summary.
    Do not write long paragraphs. Use short sentences and keep it extremely practical.

    USER FINANCIAL SUMMARY:
    {finance_str}

    WEEKLY SPENDING TREND:
    {weekly_str}

    RECENT TRANSACTIONS:
    {recent_str}
    
    7-DAY EXPENSE FORECAST:
    {forecast_str}
    
    LIVE FX & CRYPTO RATES (TRY):
    {rates_str}
    
    Format your response EXACTLY like this:
    🟢 STATUS: [Strictly 1 sentence summarizing overall financial health]
    ⚠️ RISKS: [Strictly 1-2 short bullet points on overspending, dangerous trends, or recurring costs]
    💡 ACTION: [Strictly 1-2 short bullet points with a direct command. If the user has a positive net balance, give a specific investment/hedging advice using the provided live FX or Crypto rates to protect against inflation!]
    """

    income = finance_data.get("income", 0)
    expense = finance_data.get("expense", 0)
    net_try = finance_data.get("net_try", 0)
    weekly_saving = finance_data.get("weekly_saving_avg_try", 0)
    goal = finance_data.get("goal", {})
    progress = finance_data.get("progress_percent", 0)

    if income > 0:
        expense_ratio = (expense / income) * 100
    else:
        expense_ratio = 100 if expense > 0 else 0

    if net_try >= 0 and expense_ratio <= 70:
        status = "Your balance is positive and spending is under control."
    elif net_try >= 0:
        status = "Your balance is positive, but expenses are using a high share of income."
    else:
        status = "Your balance is negative and expenses need immediate control."

    risk_lines = []
    if expense_ratio > 80:
        risk_lines.append(f"- Expenses are at {expense_ratio:.1f}% of income.")
    if weekly_saving <= 0:
        risk_lines.append("- Weekly savings are not positive yet.")
    if isinstance(forecast_data, dict) and forecast_data.get("status") == "success":
        risk_lines.append(f"- Next 7-day expense forecast is {forecast_data.get('predicted_7_days_expense', 0):,.2f} TL.")
    if not risk_lines:
        risk_lines.append("- No critical risk detected in current records.")

    usdtry = 1 / rates_data.get("usd", 1) if rates_data.get("usd", 0) > 0 else 0
    target_try = goal.get("target_try", 0)
    action_lines = []
    if net_try > target_try > 0:
        action_lines.append("- Goal is covered; move the extra balance into savings or hedging.")
    elif weekly_saving > 0:
        action_lines.append(f"- Keep saving about {weekly_saving:,.2f} TL weekly toward the goal.")
    else:
        action_lines.append("- Reduce flexible spending before adding new expenses.")
    if net_try > 0 and usdtry > 0:
        action_lines.append(f"- For inflation protection, compare part of savings against USD/TRY {usdtry:.2f}.")

    return (
        f"STATUS: {status}\n"
        f"RISKS:\n" + "\n".join(risk_lines[:2]) + "\n"
        f"ACTION:\n" + "\n".join(action_lines[:2])
    )
