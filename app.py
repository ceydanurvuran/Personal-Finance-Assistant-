import customtkinter as ctk
import requests
import cv2
import threading
import os
import mimetypes
import queue
from datetime import datetime
from tkinter import filedialog
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image, ImageDraw, ImageTk

API_URL = "http://127.0.0.1:8000"
 
access_token = None
current_username = ""
selected_transaction_id = None
all_transactions = []
sidebar_buttons = {}
last_ai_context = {}
camera_active = False
cap = None
receipt_store_entry = None
receipt_total_entry = None
receipt_category_entry = None
last_receipt_result = {
    "store": "",
    "total": 0,
    "category": ""
}
 
# --- PREMIUM TEMA PALETİ (Açık Tema, Koyu Tema) ---
THEME_BG = ("#F4F6F9", "#0D0D12")         
THEME_SIDEBAR = ("#FFFFFF", "#141419")    
THEME_CARD = ("#FFFFFF", "#1C1C24")       
THEME_ACCENT = ("#008C9E", "#00E5FF")     
THEME_INCOME = ("#27AE60", "#00FF87")     
THEME_EXPENSE = ("#E74C3C", "#FF3366")    
THEME_TEXT_MAIN = ("#2C3E50", "#FFFFFF")  
THEME_TEXT_MUTED = ("#8D99AE", "#6B6B7B") 

ctk.set_appearance_mode("dark")
 
app = ctk.CTk()
app.geometry("1400x850") # Yeni grafik alanı için yükseklik biraz artırıldı
app.title("Finance AI - Personal App")
app.configure(fg_color=THEME_BG)

window_icon_image = Image.new("RGBA", (64, 64), "#00CFE8")
window_icon_draw = ImageDraw.Draw(window_icon_image)
window_icon_draw.rounded_rectangle((4, 4, 60, 60), radius=14, fill="#00CFE8")
window_icon_draw.text((17, 15), "FA", fill="#071015")
window_icon_photo = ImageTk.PhotoImage(window_icon_image)
app.iconphoto(True, window_icon_photo)
 
def get_headers():
   return {"Authorization": f"Bearer {access_token}"}
 
def show_error(label, message):
   label.configure(text=message, text_color=THEME_EXPENSE)

def format_rate_date(value):
    if not value:
        return "Latest available"

    text = str(value).strip()
    for pattern in ("%m/%d/%Y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text[:10], pattern).strftime("%d.%m.%Y")
        except ValueError:
            continue
    return text
 
def set_active_sidebar_button(active_text):
    for text, components in sidebar_buttons.items():
        if text == active_text:
            components["btn"].configure(fg_color=("#E5E9F0", "#1F1F28"), text_color=THEME_ACCENT)
            components["indicator"].configure(fg_color=THEME_ACCENT)
        else:
            components["btn"].configure(fg_color="transparent", text_color=THEME_TEXT_MUTED)
            components["indicator"].configure(fg_color="transparent")

def make_sidebar_btn(parent, text, icon, cmd):
    # DİKKAT: Yüksekliği 40 olarak sabitledik
    btn_container = ctk.CTkFrame(parent, fg_color="transparent", height=40)
    # HAYAT KURTARAN KOD: Konteynerin esnemesini zorla engelledik!
    btn_container.pack_propagate(False) 
    
    indicator = ctk.CTkFrame(btn_container, width=4, fg_color="transparent", corner_radius=2)
    indicator.pack(side="left", fill="y", pady=4)
    
    btn = ctk.CTkButton(
        btn_container, 
        text=f"  {icon}    {text}", 
        width=210, 
        height=35, 
        fg_color="transparent", 
        text_color=THEME_TEXT_MUTED, 
        hover_color=("#E5E9F0", "#1A1A22"), 
        anchor="w", 
        font=("Segoe UI", 13, "bold"),
        corner_radius=8,
        command=cmd
    )
    # DİKKAT: expand=True parametresini tamamen kaldırdık!
    btn.pack(side="left", fill="x", padx=(8, 0)) 
    
    sidebar_buttons[text] = {"btn": btn, "indicator": indicator}
    return btn_container

def change_page(tab_name, sidebar_text=None):
    if tab_name != "ReceiptView":
        try:
            stop_camera()
        except Exception:
            pass
    main_tabview.set(tab_name)
    if sidebar_text:
        set_active_sidebar_button(sidebar_text)

def show_login():
   main_layout_frame.pack_forget()
   auth_tabview.pack(fill="both", expand=True)
   auth_tabview.set("LoginView")
  
def show_register():
   auth_tabview.set("RegisterView")
  
def show_dashboard():
   load_all_data_packages()
   change_page("DashboardView", "Dashboard")
  
def show_analytics():
   load_all_data_packages()
   change_page("AnalyticsView", "Analytics")
  
def show_transaction_screen():
   change_page("TransactionFormView", "Add Record")
  
def show_receipt_screen():
   load_uploaded_files()
   change_page("ReceiptView", "Scan Receipt")

def load_all_data_packages():
    load_transactions()
    load_summary()
    load_ai_goals()

def handle_register():
    username = reg_username_entry.get()
    password = reg_password_entry.get()
    confirm = reg_confirm_entry.get()
    if username == "" or password == "" or confirm == "":
        show_error(reg_error, "Please fill all fields")
        return
    if password != confirm:
        show_error(reg_error, "Passwords do not match")
        return
    try:
        response = requests.post(f"{API_URL}/register", json={"username": username, "password": password})
        if response.status_code == 200: show_login()
        else: show_error(reg_error, response.json().get("detail", "Register failed"))
    except Exception: show_error(reg_error, "Server error")
  
def handle_login():
    global access_token, current_username
    username = login_username_entry.get()
    password = login_password_entry.get()
    if username == "" or password == "":
        show_error(login_error, "Please fill all fields")
        return
    try:
        response = requests.post(f"{API_URL}/login", json={"username": username, "password": password})
        if response.status_code == 200:
            access_token = response.json()["access_token"]
            current_username = username
            login_error.configure(text="")
            
            auth_tabview.pack_forget()
            main_layout_frame.pack(fill="both", expand=True)
            user_name_label.configure(text=current_username.upper())
            show_dashboard()
        else:
            show_error(login_error, "Invalid username or password")
    except Exception: 
        show_error(login_error, "Server offline")

def handle_logout():
    global access_token, current_username
    access_token = None
    current_username = ""
    logout_btn.pack_forget() 
    show_login()

def load_ai_goals(force_custom=False):
    if force_custom:
        try:
            amt_str = goal_amt_entry.get().strip()
            amt = float(amt_str) if amt_str else 100.0
        except ValueError:
            amt = 100.0
        curr = goal_curr_option.get()
        url = f"{API_URL}/ai/context?target_amount={amt}&target_currency={curr}"
    else:
        url = f"{API_URL}/ai/context"

    def fetch_data():
        try:
            response = requests.get(url, headers=get_headers(), timeout=15)
            if response.status_code == 200:
                data = response.json()
                app.after(0, update_ai_ui, data)
            else:
                app.after(0, show_ai_context_error, response.text)
        except Exception as e: 
            print(f"AI Fetch Error: {e}")
            app.after(0, show_ai_context_error, str(e))
    
    threading.Thread(target=fetch_data, daemon=True).start()

def show_ai_context_error(message):
    short_message = message[:180] if message else "AI context could not be loaded."
    net_balance_lbl.configure(text="Net Balance: Data unavailable")
    crypto_balance_lbl.configure(text="Crypto equiv: Data unavailable")
    usd_try_lbl.configure(text="USD/TRY: Data unavailable")
    eur_gbp_try_lbl.configure(text="EUR/TRY: Data unavailable  |  GBP/TRY: Data unavailable")
    current_target_lbl.configure(text="Current Target: Data unavailable")
    estimated_time_lbl.configure(text="Estimated Time: Data unavailable")
    ai_saving_val_lbl.configure(text="-")
    ai_forecast_val_lbl.configure(text="-")
    ai_forecast_detail_lbl.configure(text=short_message)

def update_ai_ui(data):
    global last_ai_context
    try:
        last_ai_context = data
        ai_data = data.get("finance", {})
        rates = data.get("rates", {})
        weekly_raw = data.get("weekly", {})
        forecast_data = data.get("forecast", {})
        recent_data = data.get("recent", [])
        real_advice = data.get("ai_advice", "No advice returned.")
        
        # --- BAKİYE VE DÖVİZLER ---
        net_tl = ai_data.get("net_try", 0)
        net_usd = ai_data.get("net_usd", 0)
        net_balance_lbl.configure(text=f"{net_tl:,.2f} TL")
        
        # --- KRİPTO DÖNÜŞÜMLERİ (YENİ) ---
        net_btc = ai_data.get("net_btc", 0)
        net_eth = ai_data.get("net_eth", 0)
        if rates.get("btc", 0) > 0 and rates.get("eth", 0) > 0:
            crypto_balance_lbl.configure(
                text=f"Crypto equiv: {net_btc:.6f} BTC  |  {net_eth:.5f} ETH",
                text_color=THEME_INCOME
            )
        else:
            crypto_balance_lbl.configure(
                text="Crypto rates are temporarily unavailable",
                text_color=THEME_TEXT_MUTED
            )
        
        if rates:
            usdtry_val = rates.get('usdtry', 0)
            eurtry_val = rates.get('eurtry', 0)
            gbptry_val = rates.get('gbptry', 0)
            btc_value = rates.get('btc', 0)
            rate_source = rates.get("source", "Live service")
            rate_date = format_rate_date(rates.get("rate_date"))
            rate_state = "LIVE" if rates.get("is_live", True) else "CACHED"
            
            net_eur = ai_data.get("net_eur", net_tl / eurtry_val if eurtry_val > 0 else 0)
            net_gbp = ai_data.get("net_gbp", net_tl / gbptry_val if gbptry_val > 0 else 0)
            usd_try_lbl.configure(
                text=f"{net_usd:,.2f} USD",
                text_color=THEME_ACCENT
            )
            eur_gbp_try_lbl.configure(
                text=f"{net_eur:,.2f} EUR   |   {net_gbp:,.2f} GBP",
                text_color=THEME_TEXT_MAIN
            )
            
            usd_label.configure(text=f"1 USD = {usdtry_val:.2f} TL")
            eur_label.configure(text=f"1 EUR = {eurtry_val:.2f} TL")
            btc_label.configure(
                text=f"1 BTC = {btc_value:,.0f} TL" if btc_value > 0 else "BTC = Unavailable",
                text_color=("#D35400", "#F39C12") if btc_value > 0 else THEME_TEXT_MUTED
            )
            rates_status_label.configure(
                text=f"{rate_state}  |  {rate_source}\nRate date: {rate_date}",
                text_color=THEME_INCOME if rate_state == "LIVE" else ("#D35400", "#F39C12")
            )

        # --- HEDEF SİSTEMİ ---
        goal_obj = ai_data.get("goal", {})
        sel_amt = goal_obj.get("selected_amount", 100.0)
        sel_curr = goal_obj.get("selected_currency", "USD")
        target_in_tl = goal_obj.get("target_try", 0)
        weeks = goal_obj.get("weeks_needed", None)
        
        try:
            goal_amt_entry.delete(0, "end")
            goal_amt_entry.insert(0, str(int(sel_amt) if isinstance(sel_amt, (int, float)) and sel_amt.is_integer() else sel_amt))
            goal_curr_option.set(sel_curr.upper())
        except Exception as e:
            print("Error updating UI goal entries:", e)
        
        formatted_amt = f"{int(sel_amt):,}" if isinstance(sel_amt, (int, float)) and sel_amt.is_integer() else f"{sel_amt:,.2f}"
        current_target_lbl.configure(text=f"Current Target: {formatted_amt} {sel_curr}  ≈  {target_in_tl:,.2f} TL")
        
        if weeks is not None:
            estimated_time_lbl.configure(text=f"Estimated Time: {weeks} Weeks Needed")
        else:
            estimated_time_lbl.configure(text="Estimated Time: N/A (No weekly savings)")
        
        # --- PROGRESS BAR ---
        prog_percent = ai_data.get("progress_percent", 0)
        prog_value = max(0.0, min(1.0, prog_percent / 100.0))
        ai_progress_bar.set(prog_value)
        ai_progress_lbl.configure(
            text="Goal completed" if prog_percent >= 100 else f"Progress: {prog_percent:.1f}%"
        )

        # --- HAFTALIK TASARRUF & TAHMİN (YENİ) ---
        weekly_saving = ai_data.get("weekly_saving_avg_try", 0)
        ai_saving_val_lbl.configure(text=f"{weekly_saving:,.2f} TL")

        if isinstance(forecast_data, dict) and forecast_data.get("status") == "success":
            forecast_text = f'{forecast_data.get("predicted_7_days_expense", 0):,.2f} TL'
            forecast_detail = (
                f'Peak day: {forecast_data.get("max_expense_date", "-")}  |  '
                f'{forecast_data.get("max_expense_amount", 0):,.2f} TL'
            )
        elif isinstance(forecast_data, dict):
            forecast_text = "Insufficient data"
            forecast_detail = forecast_data.get("message", "Need more expense history.")
        else:
            forecast_text = f"{forecast_data:,.2f} TL" if isinstance(forecast_data, (int, float)) else "No forecast"
            forecast_detail = "Forecast engine returned no detail."

        ai_forecast_val_lbl.configure(text=forecast_text)
        ai_forecast_detail_lbl.configure(text=forecast_detail)
        ai_recent_count_lbl.configure(text=f"{len(recent_data)} recent records sent to AI")
        update_backend_context_panel(data)

        # --- ANALYTICS AI TEXTBOX ---
        ai_textbox.configure(state="normal")
        ai_textbox.delete("0.0", "end")
        ai_textbox.insert("0.0", real_advice)
        ai_textbox.configure(state="disabled")

        # --- 7 GÜNLÜK GELİR-GİDER GRAFİĞİ GÜNCELLEME (YENİ) ---
        update_weekly_dashboard_chart(weekly_raw)

    except Exception as e:
        print(f"UI Update Error: {e}")

def update_backend_context_panel(data):
    try:
        finance = data.get("finance", {})
        recent = data.get("recent", [])
        income = finance.get("income", 0)
        expense = finance.get("expense", 0)
        spending_rate = (expense / income * 100) if income > 0 else 0
        savings_rate = max(0, 100 - spending_rate) if income > 0 else 0

        category_totals = {}
        expense_amounts = []
        for tx in recent:
            if tx.get("type") == "expense":
                category = tx.get("category", "Other")
                amount = tx.get("amount", 0)
                category_totals[category] = category_totals.get(category, 0) + amount
                expense_amounts.append(amount)

        if category_totals:
            top_category = max(category_totals, key=category_totals.get)
            category_share = (
                category_totals[top_category] / sum(category_totals.values()) * 100
                if sum(category_totals.values()) > 0 else 0
            )
        else:
            top_category = "No expense data"
            category_share = 0

        average_expense = (
            sum(expense_amounts) / len(expense_amounts)
            if expense_amounts else 0
        )

        if income <= 0:
            efficiency_status = "NO INCOME DATA"
            efficiency_note = "Add an income record to measure efficiency."
            efficiency_color = THEME_TEXT_MUTED
        elif spending_rate <= 30:
            efficiency_status = "EXCELLENT"
            efficiency_note = "You are preserving most of your income."
            efficiency_color = THEME_INCOME
        elif spending_rate <= 60:
            efficiency_status = "HEALTHY"
            efficiency_note = "Spending is balanced and under control."
            efficiency_color = THEME_ACCENT
        else:
            efficiency_status = "NEEDS ATTENTION"
            efficiency_note = "A large share of income is being spent."
            efficiency_color = THEME_EXPENSE

        efficiency_status_value.configure(
            text=efficiency_status,
            text_color=efficiency_color
        )
        efficiency_note_label.configure(text=efficiency_note)
        efficiency_spent_value.configure(text=f"{spending_rate:.1f}%")
        efficiency_saved_value.configure(text=f"{savings_rate:.1f}%")
        efficiency_category_value.configure(
            text=f"{top_category}\n{category_share:.1f}% of recent expenses"
        )
        efficiency_average_value.configure(text=f"{average_expense:,.2f} TL")
    except Exception as e:
        print(f"Backend Context UI Error: {e}")

def update_weekly_dashboard_chart(weekly_raw):
    for widget in dash_chart_inner_frame.winfo_children(): 
        widget.destroy()
    
    if not weekly_raw:
        ctk.CTkLabel(dash_chart_inner_frame, text="No weekly data available yet.", text_color=THEME_TEXT_MUTED).pack(pady=40)
        return

    days = sorted(list(weekly_raw.keys()))
    incomes = [weekly_raw[d].get("income", 0) for d in days]
    expenses = [weekly_raw[d].get("expense", 0) for d in days]

    # Son günlerin sadece ay/gün kısmını alalım (Örn: 2026-06-05 -> 06-05)
    short_days = [d[-5:] for d in days]

    mode = ctk.get_appearance_mode()
    bg_col = THEME_CARD[1] if mode == "Dark" else THEME_CARD[0]
    text_col = THEME_TEXT_MAIN[1] if mode == "Dark" else THEME_TEXT_MAIN[0]
    muted_col = THEME_TEXT_MUTED[1] if mode == "Dark" else THEME_TEXT_MUTED[0]

    fig = Figure(figsize=(4.6, 2.15), dpi=100, facecolor=bg_col)
    ax = fig.add_subplot(111, facecolor=bg_col)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(muted_col)
    ax.spines['bottom'].set_color(muted_col)
    
    ax.plot(short_days, incomes, color=THEME_INCOME[1] if mode == "Dark" else THEME_INCOME[0], marker='o', linewidth=2, label="Income")
    ax.plot(short_days, expenses, color=THEME_EXPENSE[1] if mode == "Dark" else THEME_EXPENSE[0], marker='s', linewidth=2, label="Expense")
    ax.tick_params(colors=text_col, labelsize=8)
    ax.tick_params(axis="x", rotation=25)
    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, 1.01),
        ncol=2,
        frameon=False,
        labelcolor=text_col,
        fontsize=8,
        handlelength=1.6,
        columnspacing=1.4
    )
    ax.grid(True, linestyle='--', alpha=0.2, color=muted_col)
    fig.subplots_adjust(left=0.13, right=0.97, bottom=0.22, top=0.82)

    canvas = FigureCanvasTkAgg(fig, master=dash_chart_inner_frame)
    canvas.get_tk_widget().pack(fill="both", expand=True)

def load_summary():
   try:
       response = requests.get(f"{API_URL}/summary", headers=get_headers())
       if response.status_code == 200:
           data = response.json()
           income, expense, balance = data.get("income", 0), data.get("expense", 0), data.get("balance", 0)
           
           income_value.configure(text=f"{income:,.2f} TL", text_color=THEME_INCOME)
           expense_value.configure(text=f"{expense:,.2f} TL", text_color=THEME_EXPENSE)
           balance_value.configure(text=f"{balance:,.2f} TL", text_color=THEME_INCOME if balance >= 0 else THEME_EXPENSE)
           balance_card_frame.configure(border_color=THEME_INCOME if balance >= 0 else THEME_EXPENSE)
           transaction_count_value.configure(text=str(len(all_transactions)), text_color=THEME_ACCENT)
           
           risk_level = data.get("risk_score", "Low")
           risk_color = THEME_EXPENSE if risk_level == "High" else (("#D35400", "#F39C12") if risk_level == "Medium" else THEME_INCOME)
           risk_value.configure(text=risk_level, text_color=risk_color)
           risk_alerts = data.get("risk_alerts", [])
           risk_text = "\n".join(risk_alerts) if risk_alerts else "No risk details returned."
           analytics_risk_badge.configure(text=risk_level.upper(), text_color=risk_color)
           risk_detail_textbox.configure(state="normal")
           risk_detail_textbox.delete("0.0", "end")
           risk_detail_textbox.insert("0.0", risk_text)
           risk_detail_textbox.configure(state="disabled")
           
   except Exception: pass
 
def load_transactions():
   global all_transactions
   try:
       response = requests.get(f"{API_URL}/transactions", headers=get_headers())
       if response.status_code == 200:
           all_transactions = response.json()
           update_category_breakdown()
           update_financial_runway()
           update_transaction_table()
           update_analytics()
           transaction_count_value.configure(text=str(len(all_transactions)), text_color=THEME_ACCENT)
   except Exception: pass

def update_financial_runway():
   income = sum(t.get("amount", 0) for t in all_transactions if t.get("type") == "income")
   expenses = [t for t in all_transactions if t.get("type") == "expense"]
   expense_total = sum(t.get("amount", 0) for t in expenses)
   balance = income - expense_total

   expense_dates = []
   for transaction in expenses:
       raw_date = str(transaction.get("date", ""))[:10]
       try:
           expense_dates.append(datetime.strptime(raw_date, "%Y-%m-%d"))
       except ValueError:
           pass

   if expense_total > 0:
       observed_days = (
           max(1, (max(expense_dates) - min(expense_dates)).days + 1)
           if expense_dates else 1
       )
       daily_average = expense_total / observed_days
       runway_days = max(0, int(balance / daily_average)) if daily_average > 0 else 0
   else:
       daily_average = 0
       runway_days = 0

   if daily_average <= 0:
       status_text = "Add expense records to calculate"
       status_color = THEME_TEXT_MUTED
       runway_text = "-"
   elif runway_days >= 180:
       status_text = "Strong financial buffer"
       status_color = THEME_INCOME
       runway_text = f"{runway_days:,}"
   elif runway_days >= 90:
       status_text = "Stable financial buffer"
       status_color = THEME_INCOME
       runway_text = f"{runway_days:,}"
   elif runway_days >= 30:
       status_text = "Moderate buffer"
       status_color = ("#D35400", "#F39C12")
       runway_text = f"{runway_days:,}"
   else:
       status_text = "Low buffer"
       status_color = THEME_EXPENSE
       runway_text = f"{runway_days:,}"

   runway_days_value.configure(text=runway_text, text_color=status_color)
   runway_status_label.configure(text=status_text, text_color=status_color)
   runway_balance_value.configure(text=f"{balance:,.2f} TL")
   runway_daily_value.configure(text=f"{daily_average:,.2f} TL")
 
def get_filtered_transactions():
   search_text = search_entry.get().lower()
   filter_value = filter_option.get()
   filtered = all_transactions
   if filter_value != "All": filtered = [t for t in filtered if t["type"] == filter_value.lower()]
   if search_text != "": filtered = [t for t in filtered if search_text in t["description"].lower() or search_text in t["category"].lower()]
   return filtered
 
def update_transaction_table():
   for widget in transaction_rows_frame.winfo_children(): widget.destroy()
   header = ctk.CTkFrame(transaction_rows_frame, fg_color="transparent")
   header.pack(fill="x", pady=(0, 8))
   headers = ["Type", "Description", "Amount", "Category", "Actions"]
   column_weights = [1, 2, 2, 2, 2]
   for index, weight in enumerate(column_weights):
       header.grid_columnconfigure(index, weight=weight, uniform="transaction_columns")
   for index, title in enumerate(headers):
       ctk.CTkLabel(
           header,
           text=title,
           font=("Segoe UI", 11, "bold"),
           text_color=THEME_TEXT_MUTED,
           anchor="w"
       ).grid(row=0, column=index, sticky="ew", padx=8)

   filtered = get_filtered_transactions()
   if len(filtered) == 0:
       ctk.CTkLabel(transaction_rows_frame, text="No transactions found.", text_color=THEME_TEXT_MUTED, font=("Segoe UI", 14)).pack(pady=35)
       return

   for row in filtered[:20]:
       row_frame = ctk.CTkFrame(transaction_rows_frame, fg_color=THEME_BG, corner_radius=10, border_width=1, border_color=("#D3D8E8", "#2A2A35"))
       row_frame.pack(fill="x", pady=4)
       for index, weight in enumerate(column_weights):
           row_frame.grid_columnconfigure(index, weight=weight, uniform="transaction_columns")

       type_color = THEME_INCOME if row["type"] == "income" else THEME_EXPENSE
       ctk.CTkLabel(row_frame, text=row["type"].upper(), anchor="w", text_color=type_color, font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="ew", padx=8, pady=9)
       ctk.CTkLabel(row_frame, text=row["description"], anchor="w", text_color=THEME_TEXT_MAIN, font=("Segoe UI", 11)).grid(row=0, column=1, sticky="ew", padx=8)
       ctk.CTkLabel(row_frame, text=f'{row["amount"]:,.2f} TL', anchor="w", text_color=THEME_TEXT_MAIN, font=("Segoe UI", 11, "bold")).grid(row=0, column=2, sticky="ew", padx=8)
       ctk.CTkLabel(row_frame, text=row["category"], anchor="w", text_color=THEME_TEXT_MUTED, font=("Segoe UI", 11)).grid(row=0, column=3, sticky="ew", padx=8)
       actions_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
       actions_frame.grid(row=0, column=4, sticky="w", padx=6, pady=5)
       ctk.CTkButton(actions_frame, text="Edit", width=58, height=28, fg_color=("#3498DB", "#2C3E50"), hover_color=("#2980B9", "#34495E"), font=("Segoe UI", 10), command=lambda r=row: open_edit_transaction(r)).pack(side="left", padx=(0, 5))
       ctk.CTkButton(actions_frame, text="Delete", width=62, height=28, fg_color=("#E74C3C", "#7A2219"), hover_color=("#C0392B", "#962D22"), font=("Segoe UI", 10), command=lambda tid=row["id"]: handle_delete_transaction(tid)).pack(side="left")
 
def update_category_breakdown():
   for widget in category_list_frame.winfo_children(): widget.destroy()
   expense_categories = {}
   for transaction in all_transactions:
       if transaction["type"] == "expense":
           category = transaction["category"]
           expense_categories[category] = expense_categories.get(category, 0) + transaction["amount"]
   if len(expense_categories) == 0:
       ctk.CTkLabel(
           category_list_frame,
           text="No category data yet\nAdd expense records to generate insights.",
           text_color=THEME_TEXT_MUTED,
           font=("Segoe UI", 12)
       ).pack(anchor="w", padx=15, pady=10)
       return
   for category, amount in sorted(expense_categories.items(), key=lambda x: x[1], reverse=True)[:4]:
       ctk.CTkLabel(category_list_frame, text=f"{category}  |  {amount:,.2f} TL", font=("Segoe UI", 12), text_color=THEME_TEXT_MAIN).pack(anchor="w", padx=15, pady=3)

def update_analytics():
   for widget in analytics_chart_frame.winfo_children():
       widget.destroy()

   income, expense, category_totals = 0, 0, {}
   for transaction in all_transactions:
       amount = transaction["amount"]
       if transaction["type"] == "income":
           income += amount
       elif transaction["type"] == "expense":
           expense += amount
           category_totals[transaction["category"]] = category_totals.get(transaction["category"], 0) + amount

   balance = income - expense
   saving_rate = ((income - expense) / income * 100) if income > 0 else 0
   analytics_income_value.configure(text=f"{income:,.2f} TL")
   analytics_expense_value.configure(text=f"{expense:,.2f} TL")
   analytics_balance_value.configure(
       text=f"{balance:,.2f} TL",
       text_color=THEME_INCOME if balance >= 0 else THEME_EXPENSE
   )
   analytics_saving_value.configure(
       text=f"{saving_rate:.1f}%",
       text_color=THEME_INCOME if saving_rate >= 20 else ("#D35400", "#F39C12")
   )

   mode = ctk.get_appearance_mode()
   bg_col = THEME_CARD[1] if mode == "Dark" else THEME_CARD[0]
   muted_col = THEME_TEXT_MUTED[1] if mode == "Dark" else THEME_TEXT_MUTED[0]
   inc_col = THEME_INCOME[1] if mode == "Dark" else THEME_INCOME[0]
   exp_col = THEME_EXPENSE[1] if mode == "Dark" else THEME_EXPENSE[0]
   acc_col = THEME_ACCENT[1] if mode == "Dark" else THEME_ACCENT[0]
   text_col = THEME_TEXT_MAIN[1] if mode == "Dark" else THEME_TEXT_MAIN[0]

   fig1 = Figure(figsize=(5.7, 3.2), dpi=100, facecolor=bg_col)
   ax1 = fig1.add_subplot(111, facecolor=bg_col)
   ax1.spines['top'].set_visible(False)
   ax1.spines['right'].set_visible(False)
   ax1.spines['left'].set_color(muted_col)
   ax1.spines['bottom'].set_color(muted_col)
   bars = ax1.barh(["Expense", "Income"], [expense, income], color=[exp_col, inc_col], height=0.48)
   ax1.set_title("Cash Flow Overview", color=text_col, fontsize=13, fontweight="bold", loc="left", pad=14)
   ax1.tick_params(colors=text_col, labelsize=10)
   ax1.grid(axis="x", linestyle="--", alpha=0.16, color=muted_col)
   ax1.set_axisbelow(True)
   for bar, value in zip(bars, [expense, income]):
       ax1.text(
           bar.get_width(),
           bar.get_y() + bar.get_height() / 2,
           f"  {value:,.0f} TL",
           va="center",
           color=text_col,
           fontsize=10,
           fontweight="bold"
       )
   fig1.tight_layout()
   FigureCanvasTkAgg(fig1, master=analytics_chart_frame).get_tk_widget().pack(side="left", fill="both", expand=True, padx=(10, 5), pady=10)

   fig2 = Figure(figsize=(5.7, 3.2), dpi=100, facecolor=bg_col)
   ax2 = fig2.add_subplot(111, facecolor=bg_col)
   ax2.tick_params(colors=text_col)

   if category_totals:
       sorted_categories = sorted(category_totals.items(), key=lambda item: item[1], reverse=True)
       labels = [item[0] for item in sorted_categories[:5]]
       values = [item[1] for item in sorted_categories[:5]]
       palette = [acc_col, inc_col, "#7C5CFC", "#F39C12", "#3498DB"]
       wedges, _ = ax2.pie(
           values,
           colors=palette[:len(values)],
           startangle=90,
           wedgeprops={"width": 0.38, "edgecolor": bg_col, "linewidth": 2}
       )
       ax2.text(0, 0.06, f"{sum(values):,.0f}", ha="center", va="center", color=text_col, fontsize=15, fontweight="bold")
       ax2.text(0, -0.13, "TL spent", ha="center", va="center", color=muted_col, fontsize=9)
       ax2.legend(
           wedges,
           labels,
           loc="center left",
           bbox_to_anchor=(0.92, 0.5),
           frameon=False,
           labelcolor=text_col,
           fontsize=9
       )
       ax2.set_title("Spending by Category", color=text_col, fontsize=13, fontweight="bold", loc="left", pad=14)
   else:
       ax2.text(
           0.5,
           0.5,
           "No expense data available yet.",
           ha="center",
           va="center",
           color=text_col,
           fontsize=11
       )
       ax2.set_xticks([])
       ax2.set_yticks([])

   fig2.tight_layout()
   FigureCanvasTkAgg(fig2, master=analytics_chart_frame).get_tk_widget().pack(side="left", fill="both", expand=True, padx=(5, 10), pady=10)

def open_live_camera():
    global camera_active, cap

    if access_token is None:
        receipt_result_label.configure(
            text="Please login first.",
            text_color=THEME_EXPENSE
        )
        return

    if camera_active:
        capture_camera_image()
        return

    cap = None

    for index in [0, 1, 2]:
        temp_cap = cv2.VideoCapture(index)
        if temp_cap.isOpened():
            cap = temp_cap
            break
        temp_cap.release()

    if cap is None:
        receipt_result_label.configure(
            text="Camera could not be opened. Please check camera permission or try another device.",
            text_color=THEME_EXPENSE
        )
        return

    camera_active = True
    camera_preview_label.pack(pady=10)
    camera_btn.configure(
        text="Capture Photo",
        fg_color=THEME_INCOME,
        text_color="#FFFFFF"
    )
    receipt_result_label.configure(
        text="Camera active. Click 'Capture Photo' to scan receipt.",
        text_color=THEME_ACCENT
    )

    update_camera_frame()

def update_camera_frame():
    global cap, camera_active
    if not camera_active or cap is None:
        return
    ret, frame = cap.read()
    if ret:
        try:
            cv2_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(cv2_image)
            pil_image = pil_image.resize((600, 450))
            img_ctk = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(600, 450))
            camera_preview_label.configure(image=img_ctk)
            camera_preview_label.image = img_ctk
        except Exception as e:
            print("Camera frame conversion error:", e)
    
    app.after(30, update_camera_frame)

def poll_receipt_result(result_queue):
    try:
        result_type, payload = result_queue.get_nowait()
    except queue.Empty:
        app.after(100, poll_receipt_result, result_queue)
        return

    if result_type == "success":
        update_receipt_result_ui(
            store=payload.get("store", "-"),
            total=payload.get("total", 0),
            category=payload.get("category", "-"),
            status="Receipt read and saved to transactions."
        )
        receipt_add_btn.configure(
            text="Saved",
            state="disabled",
            fg_color=THEME_TEXT_MUTED
        )
        load_all_data_packages()
        load_uploaded_files()
        return

    receipt_result_label.configure(
        text=payload,
        text_color=THEME_EXPENSE
    )


def capture_camera_image():
    global camera_active, cap
    if not camera_active or cap is None:
        return

    ret, frame = cap.read()
    if not ret:
        receipt_result_label.configure(text="Camera capture failed.", text_color=THEME_EXPENSE)
        return

    temp_filename = "temp_receipt.jpg"
    cv2.imwrite(temp_filename, frame)

    stop_camera()
    receipt_result_label.configure(text="Reading receipt...", text_color=THEME_ACCENT)
    result_queue = queue.Queue()
    app.after(100, poll_receipt_result, result_queue)

    def process():
        try:
            with open(temp_filename, "rb") as file:
                response = requests.post(
                    f"{API_URL}/upload-receipt",
                    headers=get_headers(),
                    files={"file": ("temp_receipt.jpg", file, "image/jpeg")},
                    timeout=(10, 300)
                )

            if response.status_code == 200:
                data = response.json().get("ai_results", {})
                result_queue.put(("success", data))
            else:
                result_queue.put(("error", f"Scan failed: {response.text}"))
        except requests.exceptions.ReadTimeout:
            result_queue.put((
                "error",
                "Receipt reading took too long. Please try again after the OCR engine finishes loading."
            ))
        except Exception as e:
            result_queue.put(("error", f"Scan failed: {e}"))
        finally:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)

    threading.Thread(target=process, daemon=True).start()

def stop_camera():
    global camera_active, cap
    camera_active = False
    if cap is not None:
        cap.release()
        cap = None
    camera_preview_label.configure(image=None)
    camera_preview_label.image = None
    camera_preview_label.pack_forget()
    camera_btn.configure(text="Open Camera", fg_color=THEME_BG, text_color=THEME_TEXT_MAIN)

def update_receipt_result_ui(store="-", total="0", category="-", status="Receipt read successfully."):
    global last_receipt_result
    global receipt_store_entry, receipt_total_entry, receipt_category_entry

    last_receipt_result = {
        "store": store,
        "total": total,
        "category": category
    }

    receipt_result_label.configure(text=status, text_color=THEME_INCOME)

    receipt_store_entry.configure(state="normal")
    receipt_total_entry.configure(state="normal")
    receipt_category_entry.configure(state="normal")

    receipt_store_entry.delete(0, "end")
    receipt_store_entry.insert(0, str(store))

    receipt_total_entry.delete(0, "end")
    receipt_total_entry.insert(0, str(total))

    receipt_category_entry.delete(0, "end")
    receipt_category_entry.insert(0, str(category))

    receipt_store_entry.configure(state="disabled")
    receipt_total_entry.configure(state="disabled")
    receipt_category_entry.configure(state="disabled")


def edit_receipt_result():
    global receipt_store_entry, receipt_total_entry, receipt_category_entry
    receipt_store_entry.configure(state="normal")
    receipt_total_entry.configure(state="normal")
    receipt_category_entry.configure(state="normal")
    receipt_result_label.configure(text="You can edit the receipt values.", text_color=THEME_ACCENT)


def delete_receipt_result():
    global last_receipt_result
    global receipt_store_entry, receipt_total_entry, receipt_category_entry

    last_receipt_result = {
        "store": "",
        "total": 0,
        "category": ""
    }

    receipt_store_entry.configure(state="normal")
    receipt_total_entry.configure(state="normal")
    receipt_category_entry.configure(state="normal")

    receipt_store_entry.delete(0, "end")
    receipt_total_entry.delete(0, "end")
    receipt_category_entry.delete(0, "end")

    receipt_store_entry.configure(state="disabled")
    receipt_total_entry.configure(state="disabled")
    receipt_category_entry.configure(state="disabled")

    receipt_result_label.configure(text="Receipt result deleted.", text_color=THEME_TEXT_MUTED)


def add_receipt_to_transactions():
    receipt_result_label.configure(
        text="This receipt was already saved automatically.",
        text_color=THEME_TEXT_MUTED
    )

def upload_receipt_file():
    if access_token is None:
        receipt_result_label.configure(text="Please login first.", text_color=THEME_EXPENSE)
        return

    file_path = filedialog.askopenfilename(filetypes=[("Receipt Images", "*.jpg *.jpeg *.png")])
    if file_path == "":
        return

    receipt_result_label.configure(text="Reading receipt...", text_color=THEME_ACCENT)
    result_queue = queue.Queue()
    app.after(100, poll_receipt_result, result_queue)

    def process_upload():
        try:
            content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
            with open(file_path, "rb") as file:
                response = requests.post(
                    f"{API_URL}/upload-receipt",
                    headers=get_headers(),
                    files={"file": (os.path.basename(file_path), file, content_type)},
                    timeout=(10, 300)
                )

            if response.status_code == 200:
                data = response.json().get("ai_results", {})
                result_queue.put(("success", data))
            else:
                result_queue.put(("error", f"Upload failed: {response.text}"))
        except requests.exceptions.ReadTimeout:
            result_queue.put((
                "error",
                "Receipt reading took too long. Please try again after the OCR engine finishes loading."
            ))
        except Exception as e:
            result_queue.put(("error", f"Upload failed: {e}"))

    threading.Thread(target=process_upload, daemon=True).start()

def load_uploaded_files():
   for widget in uploaded_files_frame.winfo_children(): widget.destroy()
   try:
       response = requests.get(f"{API_URL}/files", headers=get_headers())
       for file in response.json():
           row = ctk.CTkFrame(uploaded_files_frame, fg_color=THEME_BG, corner_radius=8, border_width=1, border_color=("#D3D8E8", "#2A2A35"))
           row.pack(fill="x", pady=4)
           ctk.CTkLabel(row, text=f'#{file["id"]}  {file["filename"]}', width=260, anchor="w", font=("Arial", 13)).pack(side="left", padx=15, pady=8)
           ctk.CTkLabel(row, text="Analyzed" if file["is_analyzed"] == 1 else "Processing", width=100, anchor="w", text_color=THEME_INCOME).pack(side="left", padx=10)
           ctk.CTkLabel(row, text=file.get("uploaded_at", "-"), width=160, anchor="w", text_color=THEME_TEXT_MUTED, font=("Arial", 11)).pack(side="left", padx=10)
           ctk.CTkLabel(row, text=file.get("filepath", "-"), width=260, anchor="w", text_color=THEME_TEXT_MUTED, font=("Arial", 11)).pack(side="left", padx=10)
   except Exception: pass

def reset_transaction_form():
   global selected_transaction_id
   selected_transaction_id = None
   desc_entry.delete(0, "end")
   amount_entry.delete(0, "end")
   category_entry.delete(0, "end")
 
def open_add_transaction():
   reset_transaction_form()
   form_title_label.configure(text="Add Transaction")
   save_transaction_button.configure(text="Save")
   show_transaction_screen()
 
def open_edit_transaction(row):
   global selected_transaction_id
   selected_transaction_id = row["id"]
   
   desc_entry.delete(0, "end")
   amount_entry.delete(0, "end")
   category_entry.delete(0, "end")
   
   transaction_type_option.set(row["type"])
   desc_entry.insert(0, row["description"])
   amount_entry.insert(0, str(row["amount"]))
   category_entry.insert(0, row["category"])
   
   form_title_label.configure(text="Edit Transaction")
   save_transaction_button.configure(text="Update")
   show_transaction_screen()
 
def handle_save_transaction():
   try:
       description = desc_entry.get().strip()
       category = category_entry.get().strip()
       amount_text = amount_entry.get().strip().replace(",", ".")

       if description == "" or category == "" or amount_text == "":
           transaction_status_label.configure(
               text="Please fill all fields.",
               text_color=THEME_EXPENSE
           )
           return

       try:
           amount = float(amount_text)
       except ValueError:
           transaction_status_label.configure(
               text="Amount must be a valid number.",
               text_color=THEME_EXPENSE
           )
           return

       payload = {
           "type": transaction_type_option.get(),
           "description": description,
           "amount": amount,
           "category": category
       }

       if selected_transaction_id is None:
           response = requests.post(f"{API_URL}/transactions", json=payload, headers=get_headers())
       else:
           response = requests.put(f"{API_URL}/transactions/{selected_transaction_id}", json=payload, headers=get_headers())

       if response.status_code in [200, 201]:
           transaction_status_label.configure(
               text="Transaction saved successfully.",
               text_color=THEME_INCOME
           )
           reset_transaction_form()
           show_dashboard()
       else:
           transaction_status_label.configure(
               text="Transaction could not be saved.",
               text_color=THEME_EXPENSE
           )

   except Exception as e:
       transaction_status_label.configure(
           text=f"Save failed: {e}",
           text_color=THEME_EXPENSE
       )
 
def handle_delete_transaction(transaction_id):
   try:
       if requests.delete(f"{API_URL}/transactions/{transaction_id}", headers=get_headers()).status_code == 200: show_dashboard()
   except Exception: pass

# =========================================================================
# 🔐 GİRİŞ & KAYIT EKRANI
# =========================================================================
auth_tabview = ctk.CTkTabview(app, fg_color=THEME_BG)
auth_tabview.pack(fill="both", expand=True)

auth_tabview.add("LoginView")
auth_tabview.add("RegisterView")
auth_tabview._segmented_button.grid_forget()

login_frame = ctk.CTkFrame(auth_tabview.tab("LoginView"), fg_color=THEME_BG)
login_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.6, relheight=0.6)
login_left = ctk.CTkFrame(login_frame, fg_color=THEME_SIDEBAR, corner_radius=20)
login_left.pack(side="left", fill="both", expand=True, padx=(0, 10))
ctk.CTkLabel(
    login_left,
    text="F",
    width=72,
    height=72,
    fg_color=THEME_ACCENT,
    corner_radius=18,
    font=("Segoe UI", 38, "bold"),
    text_color=("#FFFFFF", "#071015")
).pack(pady=(100, 0))
ctk.CTkLabel(login_left, text="Finance AI", font=("Arial", 32, "bold"), text_color=THEME_TEXT_MAIN).pack(pady=(5, 10))
ctk.CTkLabel(login_left, text="Personal Finance App", font=("Arial", 14), text_color=THEME_TEXT_MUTED).pack()

login_right = ctk.CTkFrame(login_frame, fg_color=THEME_CARD, corner_radius=20)
login_right.pack(side="right", fill="both", expand=True, padx=(10, 0))
ctk.CTkLabel(login_right, text="Login", font=("Arial", 26, "bold"), text_color=THEME_TEXT_MAIN).pack(pady=(60, 30))
login_username_entry = ctk.CTkEntry(login_right, placeholder_text="Username", width=280, height=45, fg_color=THEME_BG, border_width=0, text_color=THEME_TEXT_MAIN)
login_username_entry.pack(pady=10)
login_password_entry = ctk.CTkEntry(login_right, placeholder_text="Password", show="*", width=280, height=45, fg_color=THEME_BG, border_width=0, text_color=THEME_TEXT_MAIN)
login_password_entry.pack(pady=10)
login_error = ctk.CTkLabel(login_right, text="", text_color=THEME_EXPENSE)
login_error.pack(pady=2)
ctk.CTkButton(login_right, text="Login", width=280, height=45, fg_color=THEME_ACCENT, hover_color=("#0077B6", "#00C0D0"), text_color=("#FFFFFF", "#000000"), font=("Arial", 14, "bold"), command=handle_login).pack(pady=15)
ctk.CTkButton(login_right, text="Sign Up", width=280, height=35, fg_color="transparent", hover_color=("#E5E9F0", "#2A2A35"), text_color=THEME_TEXT_MUTED, command=show_register).pack()
 
register_frame = ctk.CTkFrame(auth_tabview.tab("RegisterView"), fg_color=THEME_BG)
register_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.6, relheight=0.6)
reg_left = ctk.CTkFrame(register_frame, fg_color=THEME_SIDEBAR, corner_radius=20)
reg_left.pack(side="left", fill="both", expand=True, padx=(0, 10))
ctk.CTkLabel(
    reg_left,
    text="F",
    width=72,
    height=72,
    fg_color=THEME_ACCENT,
    corner_radius=18,
    font=("Segoe UI", 38, "bold"),
    text_color=("#FFFFFF", "#071015")
).pack(pady=(120, 0))
ctk.CTkLabel(reg_left, text="Join Us", font=("Arial", 28, "bold"), text_color=THEME_TEXT_MAIN).pack(pady=(5, 10))

reg_right = ctk.CTkFrame(register_frame, fg_color=THEME_CARD, corner_radius=20)
reg_right.pack(side="right", fill="both", expand=True, padx=(10, 0))
ctk.CTkLabel(reg_right, text="Create Account", font=("Arial", 26, "bold"), text_color=THEME_TEXT_MAIN).pack(pady=(40, 20))
reg_username_entry = ctk.CTkEntry(reg_right, placeholder_text="Username", width=280, height=42, fg_color=THEME_BG, border_width=0, text_color=THEME_TEXT_MAIN)
reg_username_entry.pack(pady=8)
reg_password_entry = ctk.CTkEntry(reg_right, placeholder_text="Password", show="*", width=280, height=42, fg_color=THEME_BG, border_width=0, text_color=THEME_TEXT_MAIN)
reg_password_entry.pack(pady=8)
reg_confirm_entry = ctk.CTkEntry(reg_right, placeholder_text="Confirm Password", show="*", width=280, height=42, fg_color=THEME_BG, border_width=0, text_color=THEME_TEXT_MAIN)
reg_confirm_entry.pack(pady=8)
reg_error = ctk.CTkLabel(reg_right, text="", text_color=THEME_EXPENSE)
reg_error.pack(pady=2)
ctk.CTkButton(reg_right, text="Sign Up", width=280, height=42, fg_color=THEME_ACCENT, hover_color=("#0077B6", "#00C0D0"), text_color=("#FFFFFF", "#000000"), font=("Arial", 14, "bold"), command=handle_register).pack(pady=10)
ctk.CTkButton(reg_right, text="Back to Login", width=280, height=35, fg_color="transparent", hover_color=("#E5E9F0", "#2A2A35"), text_color=THEME_TEXT_MUTED, command=show_login).pack()

# =========================================================================
# 🔄 ANA ARAYÜZ (SOL MENÜ & TABS)
# =========================================================================
main_layout_frame = ctk.CTkFrame(app, fg_color="transparent")

# --- SOL MENÜ ---
sidebar = ctk.CTkFrame(main_layout_frame, width=260, fg_color=THEME_SIDEBAR, corner_radius=0)
sidebar.pack(side="left", fill="y")
sidebar.pack_propagate(False)

logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
logo_frame.pack(fill="x", padx=25, pady=(20, 15))
ctk.CTkLabel(
    logo_frame,
    text="F",
    width=38,
    height=38,
    fg_color=THEME_ACCENT,
    corner_radius=10,
    font=("Segoe UI", 22, "bold"),
    text_color=("#FFFFFF", "#071015")
).pack(side="left", padx=(0, 10))
logo_text = ctk.CTkFrame(logo_frame, fg_color="transparent")
logo_text.pack(side="left")
ctk.CTkLabel(logo_text, text="Finance AI", font=("Segoe UI", 20, "bold"), text_color=THEME_TEXT_MAIN, anchor="w").pack(anchor="w")
ctk.CTkLabel(logo_text, text="APP", font=("Segoe UI", 10, "bold"), text_color=THEME_TEXT_MUTED, anchor="w").pack(anchor="w")

user_container = ctk.CTkFrame(sidebar, fg_color="transparent")
user_container.pack(fill="x", padx=20, pady=(0, 15))

profile_card = ctk.CTkFrame(user_container, fg_color=THEME_BG, height=60, corner_radius=10, cursor="hand2")
profile_card.pack(fill="x")
profile_card.pack_propagate(False)

avatar_label = ctk.CTkLabel(profile_card, text="●", font=("Arial", 24), text_color=THEME_INCOME, cursor="hand2")
avatar_label.pack(side="left", padx=(15, 10))

profile_info = ctk.CTkFrame(profile_card, fg_color="transparent", cursor="hand2")
profile_info.pack(side="left", fill="y", pady=10)

user_name_label = ctk.CTkLabel(profile_info, text="USER", font=("Segoe UI", 13, "bold"), text_color=THEME_TEXT_MAIN, cursor="hand2")
user_name_label.pack(anchor="w")
status_label = ctk.CTkLabel(profile_info, text="Online", font=("Segoe UI", 10), text_color=THEME_TEXT_MUTED, cursor="hand2")
status_label.pack(anchor="w")

logout_btn = ctk.CTkButton(user_container, text="Logout", width=220, height=35, fg_color=THEME_EXPENSE, hover_color=("#C0392B", "#C0392B"), corner_radius=8, font=("Segoe UI", 12, "bold"), command=handle_logout)

def toggle_logout_menu(event=None):
    if logout_btn.winfo_ismapped(): logout_btn.pack_forget()
    else: logout_btn.pack(fill="x", pady=(10, 0))

profile_card.bind("<Button-1>", toggle_logout_menu)
avatar_label.bind("<Button-1>", toggle_logout_menu)
profile_info.bind("<Button-1>", toggle_logout_menu)

menu_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
menu_frame.pack(fill="x", padx=10, pady=10) # DİKKAT: Burada da asla expand=True olmamalı

make_sidebar_btn(menu_frame, "Dashboard", "⊞", show_dashboard).pack(fill="x", pady=2)
make_sidebar_btn(menu_frame, "Analytics", "◠", show_analytics).pack(fill="x", pady=2)
make_sidebar_btn(menu_frame, "Add Record", "⨹", open_add_transaction).pack(fill="x", pady=2)
make_sidebar_btn(menu_frame, "Scan Receipt", "⛁", show_receipt_screen).pack(fill="x", pady=2)
spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
spacer.pack(side="top", fill="both", expand=True)

rates_container = ctk.CTkFrame(sidebar, fg_color="transparent")
rates_container.pack(side="bottom", fill="x", pady=(0, 25), padx=20)
ctk.CTkLabel(rates_container, text="MARKET DATA", font=("Segoe UI", 11, "bold"), text_color=THEME_TEXT_MUTED).pack(anchor="w", padx=5, pady=(0, 5))
rates_box = ctk.CTkFrame(rates_container, fg_color=THEME_BG, corner_radius=12)
rates_box.pack(fill="x")
usd_label = ctk.CTkLabel(rates_box, text="1 USD = Sync...", font=("Segoe UI", 13, "bold"), text_color=THEME_TEXT_MAIN)
usd_label.pack(pady=(12, 6), padx=15, anchor="w")
eur_label = ctk.CTkLabel(rates_box, text="1 EUR = Sync...", font=("Segoe UI", 13, "bold"), text_color=THEME_TEXT_MAIN)
eur_label.pack(pady=6, padx=15, anchor="w")
btc_label = ctk.CTkLabel(rates_box, text="1 BTC = Sync...", font=("Segoe UI", 13, "bold"), text_color=("#D35400", "#F39C12"))
btc_label.pack(pady=6, padx=15, anchor="w")
rates_status_label = ctk.CTkLabel(
    rates_box,
    text="Waiting for market data...",
    font=("Segoe UI", 9),
    text_color=THEME_TEXT_MUTED,
    justify="left"
)
rates_status_label.pack(pady=(2, 12), padx=15, anchor="w")

# =========================================================================
# --- SAĞ İÇERİK ANA ALANI ---
# =========================================================================
right_panel = ctk.CTkFrame(main_layout_frame, fg_color=THEME_BG)
right_panel.pack(side="right", fill="both", expand=True, padx=20)

top_header_frame = ctk.CTkFrame(right_panel, fg_color=THEME_BG, height=38)
top_header_frame.place(relx=1.0, x=-8, y=4, anchor="ne")
top_header_frame.pack_propagate(False)

def toggle_theme():
    if ctk.get_appearance_mode() == "Dark":
        ctk.set_appearance_mode("Light")
        theme_toggle_btn.configure(text="🌙 Dark Mode")
    else:
        ctk.set_appearance_mode("Dark")
        theme_toggle_btn.configure(text="☀️ Light Mode")
    if access_token: update_analytics()

theme_toggle_btn = ctk.CTkButton(top_header_frame, text="☀️ Light Mode", command=toggle_theme, width=130, height=38, fg_color=THEME_CARD, border_width=1, border_color=THEME_ACCENT, text_color=THEME_TEXT_MAIN, font=("Segoe UI", 13, "bold"), corner_radius=20)
theme_toggle_btn.pack(side="right")

main_tabview = ctk.CTkTabview(right_panel, fg_color=THEME_BG)
main_tabview.pack(fill="both", expand=True)
main_tabview.add("DashboardView")
main_tabview.add("AnalyticsView")
main_tabview.add("TransactionFormView")
main_tabview.add("ReceiptView")
main_tabview._segmented_button.grid_forget()
main_tabview.grid_rowconfigure(0, minsize=0)
main_tabview.grid_rowconfigure(1, minsize=0)
main_tabview.grid_rowconfigure(2, minsize=0)
top_header_frame.lift()

# --- PAGE 1: DASHBOARD ---
dashboard_content = ctk.CTkScrollableFrame(
    main_tabview.tab("DashboardView"),
    fg_color=THEME_BG,
    scrollbar_button_color=("#C9CED8", "#4A4B55"),
    scrollbar_button_hover_color=THEME_ACCENT
)
dashboard_content.pack(fill="both", expand=True, padx=(0, 2))

welcome_label = ctk.CTkLabel(dashboard_content, text="Dashboard", font=("Segoe UI", 30, "bold"), text_color=THEME_TEXT_MAIN)
welcome_label.pack(anchor="w", pady=(0, 0), padx=(0, 150))
ctk.CTkLabel(dashboard_content, text="Your money at a glance.", font=("Segoe UI", 13), text_color=THEME_TEXT_MUTED).pack(anchor="w", pady=(0, 8))
 
cards_frame = ctk.CTkFrame(dashboard_content, fg_color="transparent")
cards_frame.pack(fill="x", pady=(3, 5))
 
def create_card(parent, title, value_text, is_accent=False):
   bg_color = THEME_BG if is_accent else THEME_CARD
   border = THEME_ACCENT if is_accent else THEME_BG
   card = ctk.CTkFrame(parent, width=190, height=110, fg_color=bg_color, corner_radius=12, border_width=1 if is_accent else 0, border_color=border)
   card.pack(side="left", padx=6)
   card.pack_propagate(False)
   ctk.CTkLabel(card, text=title, font=("Segoe UI", 12, "bold"), text_color=THEME_TEXT_MUTED).pack(pady=(15, 5), anchor="w", padx=15)
   value = ctk.CTkLabel(card, text=value_text, font=("Segoe UI", 20, "bold"), text_color=THEME_TEXT_MAIN)
   value.pack(anchor="w", padx=15)
   return card, value
 
_, income_value = create_card(cards_frame, "Total Income", "0 TL")
_, expense_value = create_card(cards_frame, "Total Expense", "0 TL")
balance_card_frame, balance_value = create_card(cards_frame, "Balance", "0 TL", is_accent=True) 
_, risk_value = create_card(cards_frame, "Risk Score", "Low")
_, transaction_count_value = create_card(cards_frame, "Transactions", "0")
 
middle_frame = ctk.CTkFrame(dashboard_content, fg_color="transparent")
middle_frame.pack(fill="x", pady=(8, 10))
 
# KATEGORİ VE AI DETAY KUTUSU (Sol Blok)
left_middle_block = ctk.CTkFrame(middle_frame, fg_color="transparent", width=310, height=360)
left_middle_block.pack(side="left", padx=(0, 10))
left_middle_block.pack_propagate(False)

category_card = ctk.CTkFrame(left_middle_block, width=310, height=150, fg_color=THEME_CARD, corner_radius=12)
category_card.pack(side="top", fill="x", pady=(0, 10))
category_card.pack_propagate(False)
ctk.CTkLabel(category_card, text="Top Categories", font=("Segoe UI", 14, "bold"), text_color=THEME_TEXT_MAIN).pack(anchor="w", padx=15, pady=(10, 5))
category_list_frame = ctk.CTkFrame(category_card, fg_color="transparent")
category_list_frame.pack(fill="both", expand=True)

# Financial runway summary
ai_narrative_card = ctk.CTkFrame(left_middle_block, width=310, height=200, fg_color=THEME_CARD, corner_radius=12, border_width=1, border_color=THEME_ACCENT)
ai_narrative_card.pack(side="bottom", fill="x")
ai_narrative_card.pack_propagate(False)
ctk.CTkLabel(ai_narrative_card, text="Financial Runway", font=("Segoe UI", 14, "bold"), text_color=THEME_ACCENT).pack(anchor="w", padx=15, pady=(8, 0))
ctk.CTkLabel(
    ai_narrative_card,
    text="How long your current balance may last.",
    font=("Segoe UI", 10),
    text_color=THEME_TEXT_MUTED
).pack(anchor="w", padx=15, pady=(0, 0))

runway_number_frame = ctk.CTkFrame(ai_narrative_card, fg_color="transparent")
runway_number_frame.pack(fill="x", padx=15)
runway_days_value = ctk.CTkLabel(runway_number_frame, text="-", font=("Segoe UI", 30, "bold"), text_color=THEME_INCOME)
runway_days_value.pack(side="left")
ctk.CTkLabel(runway_number_frame, text=" days", font=("Segoe UI", 12, "bold"), text_color=THEME_TEXT_MUTED).pack(side="left", pady=(11, 0))

runway_status_label = ctk.CTkLabel(
    ai_narrative_card,
    text="Add expense records to calculate",
    height=23,
    fg_color=THEME_BG,
    corner_radius=7,
    font=("Segoe UI", 10, "bold"),
    text_color=THEME_TEXT_MUTED
)
runway_status_label.pack(fill="x", padx=12, pady=(0, 4))

runway_details = ctk.CTkFrame(ai_narrative_card, fg_color=THEME_BG, corner_radius=7)
runway_details.pack(fill="x", padx=12, pady=(0, 5))
ctk.CTkLabel(runway_details, text="Balance", font=("Segoe UI", 9), text_color=THEME_TEXT_MUTED).grid(row=0, column=0, sticky="w", padx=9, pady=5)
runway_balance_value = ctk.CTkLabel(runway_details, text="-", font=("Segoe UI", 9, "bold"), text_color=THEME_TEXT_MAIN)
runway_balance_value.grid(row=0, column=1, sticky="e", padx=9, pady=5)
ctk.CTkLabel(runway_details, text="Daily avg.", font=("Segoe UI", 9), text_color=THEME_TEXT_MUTED).grid(row=0, column=2, sticky="w", padx=(14, 5), pady=5)
runway_daily_value = ctk.CTkLabel(runway_details, text="-", font=("Segoe UI", 9, "bold"), text_color=THEME_TEXT_MAIN)
runway_daily_value.grid(row=0, column=3, sticky="e", padx=9, pady=5)
runway_details.grid_columnconfigure(0, weight=1)
runway_details.grid_columnconfigure(2, weight=1)
  
# AI SNAPSHOT KARTI
ai_snapshot_card = ctk.CTkFrame(middle_frame, width=350, height=360, fg_color=THEME_CARD, corner_radius=16, border_width=1, border_color="#223344")
ai_snapshot_card.pack(side="left", padx=(0, 10))
ai_snapshot_card.pack_propagate(False)

title_frame = ctk.CTkFrame(ai_snapshot_card, fg_color="transparent")
title_frame.pack(fill="x", padx=15, pady=(10, 2))
ctk.CTkLabel(title_frame, text="Balance in Other Currencies", font=("Segoe UI", 14, "bold"), text_color="#00E5FF").pack(side="left")

ctk.CTkLabel(ai_snapshot_card, text="AVAILABLE BALANCE", font=("Segoe UI", 10, "bold"), text_color=THEME_TEXT_MUTED, anchor="w").pack(fill="x", padx=15, pady=(4, 0))
net_balance_lbl = ctk.CTkLabel(ai_snapshot_card, text="-", font=("Segoe UI", 22, "bold"), text_color=THEME_INCOME, anchor="w")
net_balance_lbl.pack(fill="x", padx=15, pady=(0, 2))

usd_try_lbl = ctk.CTkLabel(ai_snapshot_card, text="- USD", font=("Segoe UI", 17, "bold"), text_color=THEME_ACCENT, anchor="w")
usd_try_lbl.pack(fill="x", padx=15, pady=(1, 0))
eur_gbp_try_lbl = ctk.CTkLabel(ai_snapshot_card, text="- EUR  |  - GBP", font=("Segoe UI", 12, "bold"), text_color=THEME_TEXT_MAIN, anchor="w")
eur_gbp_try_lbl.pack(fill="x", padx=15, pady=(0, 2))

crypto_balance_lbl = ctk.CTkLabel(ai_snapshot_card, text="Crypto equivalent: -", font=("Segoe UI", 10, "bold"), text_color=THEME_INCOME, anchor="w")
crypto_balance_lbl.pack(fill="x", padx=15, pady=(0, 3))

current_target_lbl = ctk.CTkLabel(ai_snapshot_card, text="Current Target: -", font=("Segoe UI", 12, "bold"), text_color="#FFFFFF", anchor="w")
current_target_lbl.pack(fill="x", padx=15, pady=1)
estimated_time_lbl = ctk.CTkLabel(ai_snapshot_card, text="Estimated Time: -", font=("Segoe UI", 11), text_color=THEME_TEXT_MUTED, anchor="w")
estimated_time_lbl.pack(fill="x", padx=15, pady=1)

progress_container = ctk.CTkFrame(ai_snapshot_card, fg_color="transparent")
progress_container.pack(fill="x", padx=15, pady=2)
ai_progress_bar = ctk.CTkProgressBar(progress_container, height=6, fg_color="#2A2A35", progress_color=THEME_ACCENT[1])
ai_progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))
ai_progress_lbl = ctk.CTkLabel(progress_container, text="Progress: 0%", font=("Segoe UI", 11, "bold"), text_color="#FFFFFF")
ai_progress_lbl.pack(side="right")

input_control_frame = ctk.CTkFrame(ai_snapshot_card, fg_color="transparent")
input_control_frame.pack(fill="x", padx=15, pady=(5, 5))
goal_amt_entry = ctk.CTkEntry(input_control_frame, width=80, height=28, fg_color=THEME_BG, border_width=0, text_color="#FFFFFF", font=("Segoe UI", 12))
goal_amt_entry.insert(0, "100")
goal_amt_entry.pack(side="left", padx=(0, 6))
goal_curr_option = ctk.CTkOptionMenu(input_control_frame, values=["USD", "EUR", "GBP", "TRY"], width=70, height=28, fg_color=THEME_BG, button_color=THEME_BG, text_color="#FFFFFF")
goal_curr_option.pack(side="left", padx=(0, 8))
set_goal_btn = ctk.CTkButton(input_control_frame, text="Set Goal", height=28, fg_color="#008C9E", text_color="#FFFFFF", font=("Segoe UI", 11, "bold"), corner_radius=6, command=lambda: load_ai_goals(force_custom=True))
set_goal_btn.pack(side="right", fill="x", expand=True)
 
# AI PROJECTIONS KARTI
quick_card = ctk.CTkFrame(middle_frame, height=360, fg_color=THEME_CARD, corner_radius=12)
quick_card.pack(side="left", fill="both", expand=True)
quick_card.pack_propagate(False)
ctk.CTkLabel(quick_card, text="Forecast & Planning", font=("Segoe UI", 16, "bold"), text_color=THEME_TEXT_MAIN).pack(anchor="w", padx=20, pady=(14, 2))
ctk.CTkLabel(
    quick_card,
    text="Uses recent spending days to estimate next week's expense.",
    font=("Segoe UI", 11),
    text_color=THEME_TEXT_MUTED
).pack(anchor="w", padx=20, pady=(0, 8))

projection_frame = ctk.CTkFrame(quick_card, fg_color=THEME_BG, corner_radius=10)
projection_frame.pack(fill="both", expand=True, padx=20, pady=(8, 20))
ctk.CTkLabel(projection_frame, text="AI Projections", font=("Segoe UI", 12, "bold"), text_color=THEME_ACCENT).pack(anchor="w", padx=15, pady=(6, 2))

proj_sub1 = ctk.CTkFrame(projection_frame, fg_color="transparent")
proj_sub1.pack(fill="x", padx=15, pady=2)
ctk.CTkLabel(proj_sub1, text="Weekly Savings Avg:", font=("Segoe UI", 12), text_color=THEME_TEXT_MUTED).pack(side="left")
ai_saving_val_lbl = ctk.CTkLabel(proj_sub1, text="-", font=("Segoe UI", 13, "bold"), text_color=THEME_INCOME)
ai_saving_val_lbl.pack(side="right")

proj_sub2 = ctk.CTkFrame(projection_frame, fg_color="transparent")
proj_sub2.pack(fill="x", padx=15, pady=2)
ctk.CTkLabel(proj_sub2, text="Next Week Expense Forecast:", font=("Segoe UI", 12), text_color=THEME_TEXT_MUTED).pack(side="left")
ai_forecast_val_lbl = ctk.CTkLabel(proj_sub2, text="-", font=("Segoe UI", 13, "bold"), text_color=THEME_EXPENSE)
ai_forecast_val_lbl.pack(side="right")

ai_forecast_detail_lbl = ctk.CTkLabel(projection_frame, text="", font=("Segoe UI", 11), text_color=THEME_TEXT_MUTED, anchor="w")
ai_forecast_detail_lbl.pack(fill="x", padx=15, pady=(2, 0))
ai_recent_count_lbl = ctk.CTkLabel(projection_frame, text="", font=("Segoe UI", 11), text_color=THEME_TEXT_MUTED, anchor="w")
ai_recent_count_lbl.pack(fill="x", padx=15, pady=(0, 4))

# TABLO VE 7 GÜNLÜK GRAFİK ALANI (Alt Blok)
bottom_layout_frame = ctk.CTkFrame(dashboard_content, fg_color="transparent")
bottom_layout_frame.pack(fill="both", expand=True, pady=(5, 8), before=middle_frame)

# 🛠️ EKLENTİ: Son 7 Günlük Gelir Gider Analizi Grafiği (weekly_data için)
dash_chart_card = ctk.CTkFrame(bottom_layout_frame, width=360, height=245, fg_color=THEME_CARD, corner_radius=12)
dash_chart_card.pack(side="left", fill="y", padx=(0, 10))
dash_chart_card.pack_propagate(False)
ctk.CTkLabel(dash_chart_card, text="7-Day Historical Trend Analysis", font=("Segoe UI", 14, "bold"), text_color=THEME_TEXT_MAIN).pack(anchor="w", padx=15, pady=(10, 2))
dash_chart_inner_frame = ctk.CTkFrame(dash_chart_card, fg_color="transparent")
dash_chart_inner_frame.pack(fill="both", expand=True, padx=10, pady=5)

transactions_card = ctk.CTkFrame(bottom_layout_frame, height=260, fg_color=THEME_CARD, corner_radius=12)
transactions_card.pack(side="right", fill="both", expand=True)
table_top = ctk.CTkFrame(transactions_card, fg_color="transparent")
table_top.pack(fill="x", padx=15, pady=(10, 5))
ctk.CTkLabel(table_top, text="Recent Transactions", font=("Segoe UI", 15, "bold"), text_color=THEME_TEXT_MAIN).pack(side="left")
search_entry = ctk.CTkEntry(table_top, placeholder_text="Search logs...", width=160, height=30, fg_color=THEME_BG, border_width=0, text_color=THEME_TEXT_MAIN)
search_entry.pack(side="right", padx=(8, 0))
filter_option = ctk.CTkOptionMenu(table_top, values=["All", "income", "expense"], width=90, height=30, fg_color=THEME_BG, button_color=THEME_BG, text_color=THEME_TEXT_MAIN, command=lambda v: update_transaction_table())
filter_option.pack(side="right")
search_entry.bind("<KeyRelease>", lambda event: update_transaction_table())

transaction_rows_frame = ctk.CTkScrollableFrame(transactions_card, height=210)
transaction_rows_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

# --- PAGE 2: ANALYTICS ---
analytics_content = ctk.CTkScrollableFrame(main_tabview.tab("AnalyticsView"), fg_color=THEME_BG)
analytics_content.pack(fill="both", expand=True)

analytics_top_bar = ctk.CTkFrame(analytics_content, fg_color=THEME_BG)
analytics_top_bar.pack(fill="x", pady=(0, 15))
analytics_heading = ctk.CTkFrame(analytics_top_bar, fg_color="transparent")
analytics_heading.pack(side="left")
ctk.CTkLabel(analytics_heading, text="Analytics", font=("Segoe UI", 30, "bold"), text_color=THEME_TEXT_MAIN).pack(anchor="w")
ctk.CTkLabel(
    analytics_heading,
    text="Understand where your money goes and what to do next.",
    font=("Segoe UI", 12),
    text_color=THEME_TEXT_MUTED
).pack(anchor="w", pady=(2, 0))
ctk.CTkButton(
    analytics_top_bar,
    text="Refresh Insights",
    width=130,
    height=36,
    fg_color=THEME_ACCENT,
    text_color=("#FFFFFF", "#000000"),
    font=("Segoe UI", 12, "bold"),
    command=load_all_data_packages
).pack(side="right", pady=5)

analytics_kpi_frame = ctk.CTkFrame(analytics_content, fg_color="transparent")
analytics_kpi_frame.pack(fill="x", pady=(0, 12))

def create_analytics_kpi(parent, title, subtitle, color):
    card = ctk.CTkFrame(
        parent,
        height=118,
        fg_color=THEME_CARD,
        corner_radius=14,
        border_width=1,
        border_color=("#E3E7EF", "#292A35")
    )
    card.pack(side="left", fill="x", expand=True, padx=5)
    card.pack_propagate(False)
    ctk.CTkFrame(card, width=5, height=70, fg_color=color, corner_radius=3).pack(side="left", padx=(14, 10), pady=24)
    text_frame = ctk.CTkFrame(card, fg_color="transparent")
    text_frame.pack(side="left", fill="both", expand=True, pady=18)
    ctk.CTkLabel(text_frame, text=title, font=("Segoe UI", 11, "bold"), text_color=THEME_TEXT_MUTED).pack(anchor="w")
    value = ctk.CTkLabel(text_frame, text="-", font=("Segoe UI", 20, "bold"), text_color=color)
    value.pack(anchor="w", pady=(5, 2))
    ctk.CTkLabel(text_frame, text=subtitle, font=("Segoe UI", 10), text_color=THEME_TEXT_MUTED).pack(anchor="w")
    return value

analytics_income_value = create_analytics_kpi(analytics_kpi_frame, "TOTAL INCOME", "All recorded income", THEME_INCOME)
analytics_expense_value = create_analytics_kpi(analytics_kpi_frame, "TOTAL EXPENSE", "All recorded spending", THEME_EXPENSE)
analytics_balance_value = create_analytics_kpi(analytics_kpi_frame, "NET BALANCE", "Income minus expenses", THEME_ACCENT)
analytics_saving_value = create_analytics_kpi(analytics_kpi_frame, "SAVINGS RATE", "Healthy target: 20%+", ("#D35400", "#F39C12"))

risk_detail_card = ctk.CTkFrame(analytics_content, fg_color=THEME_CARD, corner_radius=12, border_width=1, border_color=("#D3D8E8", "#2A2A35"))
risk_detail_card.pack(fill="x", pady=10)
analytics_risk_header = ctk.CTkFrame(risk_detail_card, fg_color="transparent")
analytics_risk_header.pack(fill="x", padx=20, pady=(14, 4))
ctk.CTkLabel(analytics_risk_header, text="Risk Monitor", font=("Segoe UI", 16, "bold"), text_color=THEME_TEXT_MAIN).pack(side="left")
analytics_risk_badge = ctk.CTkLabel(
    analytics_risk_header,
    text="CHECKING",
    width=90,
    height=26,
    fg_color=THEME_BG,
    corner_radius=13,
    font=("Segoe UI", 10, "bold"),
    text_color=THEME_TEXT_MUTED
)
analytics_risk_badge.pack(side="right")
ctk.CTkLabel(
    risk_detail_card,
    text="Repeated charges and unusual spending patterns appear here.",
    font=("Segoe UI", 11),
    text_color=THEME_TEXT_MUTED
).pack(anchor="w", padx=20, pady=(0, 8))
risk_detail_textbox = ctk.CTkTextbox(risk_detail_card, height=90, fg_color=THEME_BG, text_color=THEME_TEXT_MAIN, font=("Segoe UI", 12), corner_radius=8)
risk_detail_textbox.pack(fill="x", padx=15, pady=(0, 12))
risk_detail_textbox.insert("0.0", "")
risk_detail_textbox.configure(state="disabled")

charts_card = ctk.CTkFrame(analytics_content, fg_color=THEME_CARD, corner_radius=14)
charts_card.pack(fill="x", pady=15)
analytics_chart_frame = ctk.CTkFrame(charts_card, fg_color="transparent")
analytics_chart_frame.pack(fill="both", expand=True, padx=10, pady=10)

backend_context_card = ctk.CTkFrame(analytics_content, fg_color=THEME_CARD, corner_radius=12, border_width=1, border_color=THEME_ACCENT)
backend_context_card.pack(fill="x", pady=10)
efficiency_header = ctk.CTkFrame(backend_context_card, fg_color="transparent")
efficiency_header.pack(fill="x", padx=20, pady=(14, 2))
ctk.CTkLabel(efficiency_header, text="Spending Efficiency Analysis", font=("Segoe UI", 16, "bold"), text_color=THEME_ACCENT).pack(side="left")
efficiency_status_value = ctk.CTkLabel(
    efficiency_header,
    text="CALCULATING",
    width=125,
    height=28,
    fg_color=THEME_BG,
    corner_radius=14,
    font=("Segoe UI", 10, "bold"),
    text_color=THEME_TEXT_MUTED
)
efficiency_status_value.pack(side="right")
ctk.CTkLabel(
    backend_context_card,
    text="How efficiently your income is being managed.",
    font=("Segoe UI", 11),
    text_color=THEME_TEXT_MUTED
).pack(anchor="w", padx=20, pady=(0, 2))
efficiency_note_label = ctk.CTkLabel(
    backend_context_card,
    text="Waiting for financial data...",
    font=("Segoe UI", 12, "bold"),
    text_color=THEME_TEXT_MAIN
)
efficiency_note_label.pack(anchor="w", padx=20, pady=(0, 10))

efficiency_metrics_frame = ctk.CTkFrame(backend_context_card, fg_color="transparent")
efficiency_metrics_frame.pack(fill="x", padx=14, pady=(0, 14))

def create_efficiency_metric(parent, title, color):
    metric = ctk.CTkFrame(
        parent,
        height=105,
        fg_color=THEME_BG,
        corner_radius=10,
        border_width=1,
        border_color=("#D3D8E8", "#292A35")
    )
    metric.pack(side="left", fill="x", expand=True, padx=6)
    metric.pack_propagate(False)
    ctk.CTkLabel(
        metric,
        text=title,
        font=("Segoe UI", 10, "bold"),
        text_color=THEME_TEXT_MUTED
    ).pack(anchor="w", padx=14, pady=(14, 5))
    value = ctk.CTkLabel(
        metric,
        text="-",
        font=("Segoe UI", 17, "bold"),
        text_color=color,
        justify="left"
    )
    value.pack(anchor="w", padx=14)
    return value

efficiency_spent_value = create_efficiency_metric(efficiency_metrics_frame, "INCOME SPENT", THEME_EXPENSE)
efficiency_saved_value = create_efficiency_metric(efficiency_metrics_frame, "INCOME PRESERVED", THEME_INCOME)
efficiency_category_value = create_efficiency_metric(efficiency_metrics_frame, "CATEGORY CONCENTRATION", THEME_ACCENT)
efficiency_average_value = create_efficiency_metric(efficiency_metrics_frame, "AVERAGE EXPENSE", ("#D35400", "#F39C12"))

ai_advice_card = ctk.CTkFrame(analytics_content, fg_color=THEME_BG, corner_radius=12, border_width=1, border_color=THEME_ACCENT)
ai_advice_card.pack(fill="x", pady=15)
ctk.CTkLabel(ai_advice_card, text="AI Action Plan", font=("Segoe UI", 16, "bold"), text_color=THEME_ACCENT).pack(anchor="w", padx=20, pady=(16, 2))
ctk.CTkLabel(
    ai_advice_card,
    text="Short, practical recommendations based on your current records.",
    font=("Segoe UI", 11),
    text_color=THEME_TEXT_MUTED
).pack(anchor="w", padx=20, pady=(0, 8))

ai_textbox = ctk.CTkTextbox(ai_advice_card, height=140, fg_color=THEME_CARD, text_color=THEME_TEXT_MAIN, font=("Segoe UI", 13), corner_radius=8)
ai_textbox.pack(fill="x", padx=15, pady=(0, 15))
ai_textbox.insert("0.0", "")
ai_textbox.configure(state="disabled")

# --- PAGE 3: RECEIPT VIEW ---
receipt_content = ctk.CTkScrollableFrame(main_tabview.tab("ReceiptView"), fg_color=THEME_BG)
receipt_content.pack(fill="both", expand=True)

receipt_top_bar = ctk.CTkFrame(receipt_content, fg_color=THEME_BG)
receipt_top_bar.pack(fill="x", pady=(0, 15))
ctk.CTkLabel(receipt_top_bar, text="Scan Receipt", font=("Segoe UI", 30, "bold"), text_color=THEME_TEXT_MAIN).pack(side="left")

receipt_card = ctk.CTkFrame(receipt_content, fg_color=THEME_CARD, corner_radius=12)
receipt_card.pack(fill="both", expand=True, pady=10)

action_box = ctk.CTkFrame(receipt_card, fg_color="transparent")
action_box.pack(fill="x", padx=25, pady=30)
ctk.CTkButton(action_box, text="Upload File", width=220, height=45, fg_color=THEME_ACCENT, text_color=("#FFFFFF", "#000000"), font=("Segoe UI", 14, "bold"), corner_radius=8, command=upload_receipt_file).pack(side="left", padx=(0, 15))
camera_btn = ctk.CTkButton(action_box, text="Open Camera", width=220, height=45, fg_color=THEME_BG, text_color=THEME_TEXT_MAIN, font=("Segoe UI", 14, "bold"), corner_radius=8, command=open_live_camera)
camera_btn.pack(side="left")

camera_preview_label = ctk.CTkLabel(receipt_card, text="")

receipt_result_label = ctk.CTkLabel(receipt_card, text="Ready to scan.", font=("Courier", 13), text_color=THEME_TEXT_MUTED)
receipt_result_label.pack(anchor="w", padx=25, pady=(0, 20))
receipt_result_card = ctk.CTkFrame(receipt_card, fg_color=THEME_BG, corner_radius=12, border_width=1, border_color=THEME_ACCENT)
receipt_result_card.pack(fill="x", padx=25, pady=(0, 20))

ctk.CTkLabel(
    receipt_result_card,
    text="Receipt Result",
    font=("Segoe UI", 15, "bold"),
    text_color=THEME_ACCENT
).pack(anchor="w", padx=15, pady=(12, 5))

receipt_fields_frame = ctk.CTkFrame(receipt_result_card, fg_color="transparent")
receipt_fields_frame.pack(fill="x", padx=15, pady=5)

ctk.CTkLabel(receipt_fields_frame, text="Store", text_color=THEME_TEXT_MUTED).grid(row=0, column=0, sticky="w", padx=5)
ctk.CTkLabel(receipt_fields_frame, text="Total", text_color=THEME_TEXT_MUTED).grid(row=0, column=1, sticky="w", padx=5)
ctk.CTkLabel(receipt_fields_frame, text="Category", text_color=THEME_TEXT_MUTED).grid(row=0, column=2, sticky="w", padx=5)

receipt_store_entry = ctk.CTkEntry(receipt_fields_frame, width=220, height=35, fg_color=THEME_CARD, text_color=THEME_TEXT_MAIN)
receipt_store_entry.grid(row=1, column=0, padx=5, pady=5)

receipt_total_entry = ctk.CTkEntry(receipt_fields_frame, width=140, height=35, fg_color=THEME_CARD, text_color=THEME_TEXT_MAIN)
receipt_total_entry.grid(row=1, column=1, padx=5, pady=5)

receipt_category_entry = ctk.CTkEntry(receipt_fields_frame, width=180, height=35, fg_color=THEME_CARD, text_color=THEME_TEXT_MAIN)
receipt_category_entry.grid(row=1, column=2, padx=5, pady=5)

receipt_store_entry.configure(state="disabled")
receipt_total_entry.configure(state="disabled")
receipt_category_entry.configure(state="disabled")

receipt_action_frame = ctk.CTkFrame(receipt_result_card, fg_color="transparent")
receipt_action_frame.pack(anchor="e", padx=15, pady=(5, 12))

ctk.CTkButton(
    receipt_action_frame,
    text="Edit",
    width=80,
    height=32,
    fg_color=("#3498DB", "#2C3E50"),
    command=edit_receipt_result
).pack(side="left", padx=5)

ctk.CTkButton(
    receipt_action_frame,
    text="Delete",
    width=80,
    height=32,
    fg_color=THEME_EXPENSE,
    command=delete_receipt_result
).pack(side="left", padx=5)

receipt_add_btn = ctk.CTkButton(
    receipt_action_frame,
    text="Auto Saved",
    width=100,
    height=32,
    fg_color=THEME_TEXT_MUTED,
    text_color="#000000",
    command=add_receipt_to_transactions,
    state="disabled"
)
receipt_add_btn.pack(side="left", padx=5)

def toggle_receipt_history():
    if not hasattr(toggle_receipt_history, "is_open"): toggle_receipt_history.is_open = False
    if toggle_receipt_history.is_open:
        uploaded_files_frame.pack_forget()
        history_toggle_btn.configure(text="View Processed Files")
        toggle_receipt_history.is_open = False
    else:
        uploaded_files_frame.pack(fill="both", expand=True, padx=25, pady=(5, 15))
        history_toggle_btn.configure(text="Hide Processed Files")
        toggle_receipt_history.is_open = True

history_toggle_btn = ctk.CTkButton(receipt_card, text="View Processed Files", width=300, height=40, fg_color=THEME_BG, text_color=THEME_TEXT_MAIN, corner_radius=8, font=("Segoe UI", 13, "bold"), command=toggle_receipt_history)
history_toggle_btn.pack(pady=(0, 20))
uploaded_files_frame = ctk.CTkFrame(receipt_card, fg_color="transparent")

# --- PAGE 4: TRANSACTION FORM ---
transaction_content = ctk.CTkFrame(main_tabview.tab("TransactionFormView"), fg_color=THEME_BG)
transaction_content.pack(fill="both", expand=True)

form_top_bar = ctk.CTkFrame(transaction_content, fg_color=THEME_BG)
form_top_bar.pack(fill="x", pady=(0, 15))
form_title_label = ctk.CTkLabel(form_top_bar, text="Add Transaction", font=("Segoe UI", 30, "bold"), text_color=THEME_TEXT_MAIN)
form_title_label.pack(side="left")

transaction_frame = ctk.CTkFrame(transaction_content, width=450, height=650, fg_color=THEME_CARD, corner_radius=16)
transaction_frame.place(relx=0.5, rely=0.5, anchor="center")
transaction_frame.pack_propagate(False)

ctk.CTkLabel(transaction_frame, text="Transaction Details", font=("Segoe UI", 20, "bold"), text_color=THEME_TEXT_MAIN).pack(pady=(35, 20))
ctk.CTkLabel(transaction_frame, text="Transaction Type", text_color=THEME_TEXT_MUTED, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=65)
transaction_type_option = ctk.CTkOptionMenu(transaction_frame, values=["income", "expense"], width=320, height=45, fg_color=THEME_BG, button_color=THEME_BG, text_color=THEME_TEXT_MAIN)
transaction_type_option.pack(pady=(3, 10))

ctk.CTkLabel(transaction_frame, text="Description", text_color=THEME_TEXT_MUTED, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=65)
desc_entry = ctk.CTkEntry(transaction_frame, placeholder_text="Description (e.g. Market)", width=320, height=45, fg_color=THEME_BG, border_width=0, text_color=THEME_TEXT_MAIN)
desc_entry.pack(pady=(3, 10))

ctk.CTkLabel(transaction_frame, text="Amount", text_color=THEME_TEXT_MUTED, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=65)
amount_entry = ctk.CTkEntry(transaction_frame, placeholder_text="Amount", width=320, height=45, fg_color=THEME_BG, border_width=0, text_color=THEME_TEXT_MAIN)
amount_entry.pack(pady=(3, 10))

ctk.CTkLabel(transaction_frame, text="Category", text_color=THEME_TEXT_MUTED, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=65)
category_entry = ctk.CTkEntry(transaction_frame, placeholder_text="Category", width=320, height=45, fg_color=THEME_BG, border_width=0, text_color=THEME_TEXT_MAIN)
category_entry.pack(pady=(3, 10))

transaction_status_label = ctk.CTkLabel(
    transaction_frame,
    text="",
    font=("Segoe UI", 11),
    text_color=THEME_TEXT_MUTED
)
transaction_status_label.pack(pady=(2, 0))

save_transaction_button = ctk.CTkButton(transaction_frame, text="Save", width=320, height=45, fg_color=THEME_ACCENT, text_color=("#FFFFFF", "#000000"), font=("Segoe UI", 14, "bold"), corner_radius=8, command=handle_save_transaction)
save_transaction_button.pack(pady=(12, 30))

show_login()
app.mainloop()
