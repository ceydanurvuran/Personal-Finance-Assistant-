import customtkinter as ctk
import requests
import cv2
import threading
import os
from tkinter import filedialog
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
 
API_URL = "http://127.0.0.1:8000"
 
access_token = None
current_username = ""
selected_transaction_id = None
all_transactions = []
sidebar_buttons = {}
recent_uploaded_files = []
show_receipt_history = False
 
# --- PREMIUM NEON DARK RENK PALETİ ---
THEME_BG = "#121214"         
THEME_SIDEBAR = "#1A1A1E"    
THEME_CARD = "#22222A"       
THEME_ACCENT = "#00ADB5"     
THEME_INCOME = "#2ECC71"     
THEME_EXPENSE = "#E74C3C"    
THEME_TEXT_MAIN = "#FFFFFF"  
THEME_TEXT_MUTED = "#8B8B9A" 

ctk.set_appearance_mode("dark")
 
app = ctk.CTk()
app.geometry("1400x850")
app.title("Personal Financial Assistant")
app.configure(fg_color=THEME_BG)
 
def get_headers():
   return {"Authorization": f"Bearer {access_token}"}
 
def show_error(label, message):
   label.configure(text=message, text_color=THEME_EXPENSE)
 
def set_active_sidebar_button(active_text):
    for text, btn in sidebar_buttons.items():
        if text == active_text:
            btn.configure(
                fg_color="#25252D", 
                text_color=THEME_ACCENT, 
                border_width=1, 
                border_color=THEME_ACCENT
            )
        else:
            btn.configure(
                fg_color="transparent", 
                text_color=THEME_TEXT_MAIN, 
                border_width=0
            )

def make_sidebar_btn(parent, text, cmd):
    btn = ctk.CTkButton(
        parent, 
        text=text, 
        width=210, 
        height=46, 
        fg_color="transparent", 
        text_color=THEME_TEXT_MAIN, 
        hover_color="#22222A", 
        anchor="w", 
        font=("Arial", 14, "bold"),
        corner_radius=12,
        command=cmd
    )
    sidebar_buttons[text] = btn
    return btn

def change_page(tab_name, sidebar_text=None):
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
   change_page("DashboardView", "  📊  Dashboard")
 
def show_analytics():
   load_all_data_packages()
   change_page("AnalyticsView", "  📈  Analytics")
 
def show_transaction_screen():
   change_page("TransactionFormView", "  ➕  Add Transaction")
 
def show_receipt_screen():
   load_uploaded_files()
   change_page("ReceiptView", "  🧾  Receipt Upload")

def load_all_data_packages():
    load_summary()
    load_transactions()
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
           main_layout_frame.pack(fill="both", expand=True, padx=30, pady=30)
           user_name_label.configure(text=current_username.upper())
           show_dashboard()
       else:
           show_error(login_error, "Invalid username or password")
   except Exception: show_error(login_error, "Server offline")
 
def handle_logout():
   global access_token, current_username
   access_token = None
   current_username = ""
   show_login()

def set_ai_goal_from_inputs():
    """AI hedef kartındaki kullanıcı hedefini günceller."""
    global ai_target_amount, ai_target_currency
    try:
        value = float(ai_target_entry.get().replace(",", "."))
        if value <= 0:
            ai_estimate_val.configure(text="Target amount must be greater than 0", text_color=THEME_EXPENSE)
            return
        ai_target_amount = value
        ai_target_currency = ai_currency_option.get()
        load_ai_goals()
    except Exception:
        ai_estimate_val.configure(text="Please enter a valid target amount", text_color=THEME_EXPENSE)


def _fetch_frontend_rates():
    """Backend kur servisi cevap vermezse frontend tarafında yedek kur denemesi yapar."""
    try:
        fx_res = requests.get(
            "https://api.frankfurter.app/latest?from=TRY&to=USD,EUR,GBP",
            timeout=6
        )
        fx_res.raise_for_status()
        fx = fx_res.json().get("rates", {})
        return {
            "usd": fx.get("USD", 0),
            "eur": fx.get("EUR", 0),
            "gbp": fx.get("GBP", 0)
        }
    except Exception:
        return {}


def _rate_to_try(rates, currency):
    key = currency.lower()
    if key == "try":
        return 1
    rate = rates.get(key, 0)
    if rate and rate > 0:
        return 1 / rate
    return 0


def load_ai_goals():
    """AI Financial Snapshot kartını günceller: kur, USD dönüşümü ve kullanıcı hedefi."""
    target_amount = ai_target_amount
    target_currency = ai_target_currency

    try:
        response = requests.get(
            f"{API_URL}/ai/context?target_amount={target_amount}&target_currency={target_currency}",
            headers=get_headers(),
            timeout=8
        )

        if response.status_code == 200:
            payload = response.json()
            ai_data = payload.get("finance", {})
            rates = payload.get("rates", {})
            goal = ai_data.get("goal", {})

            net_try = float(ai_data.get("net_try", 0) or 0)
            net_usd = float(ai_data.get("net_usd", 0) or 0)
            usd_try = _rate_to_try(rates, "USD")
            eur_try = _rate_to_try(rates, "EUR")
            gbp_try = _rate_to_try(rates, "GBP")

            target_try = goal.get("target_try")
            weeks_needed = goal.get("weeks_needed")

            ai_goal_val.configure(
                text=f"Net Balance: {net_try:.2f} TL  ≈  {net_usd:.2f} USD",
                text_color=THEME_TEXT_MAIN
            )
            ai_weeks_val.configure(
                text=f"USD/TRY: {usd_try:.2f} TL" if usd_try else "USD/TRY: unavailable",
                text_color=THEME_TEXT_MUTED
            )
            ai_rates_val.configure(
                text=f"EUR/TRY: {eur_try:.2f} TL   |   GBP/TRY: {gbp_try:.2f} TL" if eur_try and gbp_try else "EUR/GBP rates unavailable",
                text_color=THEME_TEXT_MUTED
            )
            ai_target_val.configure(
                text=f"Current Target: {target_amount:g} {target_currency}"
                     + (f"  ≈  {float(target_try):.2f} TL" if target_try is not None else ""),
                text_color=THEME_TEXT_MAIN
            )
            ai_estimate_val.configure(
                text="Estimated Time: No weekly saving stream" if weeks_needed is None else f"Estimated Time: {weeks_needed} weeks",
                text_color=THEME_ACCENT
            )
            return
        else:
            print("AI context error:", response.status_code, response.text)

    except Exception as e:
        print("AI context request failed:", e)

    # Backend AI context çalışmazsa: /summary + frontend yedek kur servisi ile yine kur ve hedef göster.
    try:
        summary_res = requests.get(f"{API_URL}/summary", headers=get_headers(), timeout=5)
        if summary_res.status_code == 200:
            data = summary_res.json()
            net_try = float(data.get("balance", 0) or 0)
            rates = _fetch_frontend_rates()
            usd_try = _rate_to_try(rates, "USD")
            eur_try = _rate_to_try(rates, "EUR")
            gbp_try = _rate_to_try(rates, "GBP")

            if usd_try:
                net_usd = net_try / usd_try
                target_try = target_amount * _rate_to_try(rates, target_currency)
                ai_goal_val.configure(text=f"Net Balance: {net_try:.2f} TL  ≈  {net_usd:.2f} USD", text_color=THEME_TEXT_MAIN)
                ai_weeks_val.configure(text=f"USD/TRY: {usd_try:.2f} TL", text_color=THEME_TEXT_MUTED)
                ai_rates_val.configure(
                    text=f"EUR/TRY: {eur_try:.2f} TL   |   GBP/TRY: {gbp_try:.2f} TL" if eur_try and gbp_try else "EUR/GBP rates unavailable",
                    text_color=THEME_TEXT_MUTED
                )
                ai_target_val.configure(text=f"Current Target: {target_amount:g} {target_currency}  ≈  {target_try:.2f} TL", text_color=THEME_TEXT_MAIN)
                ai_estimate_val.configure(text="Estimated Time: backend weekly calculation unavailable", text_color=THEME_TEXT_MUTED)
            else:
                ai_goal_val.configure(text=f"Net Balance: {net_try:.2f} TL", text_color=THEME_TEXT_MAIN)
                ai_weeks_val.configure(text="USD/TRY: unavailable", text_color=THEME_TEXT_MUTED)
                ai_rates_val.configure(text="Currency service could not be reached", text_color=THEME_TEXT_MUTED)
                ai_target_val.configure(text=f"Current Target: {target_amount:g} {target_currency}", text_color=THEME_TEXT_MAIN)
                ai_estimate_val.configure(text="Estimated Time: unavailable", text_color=THEME_TEXT_MUTED)
        else:
            ai_goal_val.configure(text="Finance data unavailable", text_color=THEME_EXPENSE)
            ai_weeks_val.configure(text="Please sync again", text_color=THEME_TEXT_MUTED)
            ai_rates_val.configure(text="", text_color=THEME_TEXT_MUTED)
            ai_target_val.configure(text="", text_color=THEME_TEXT_MUTED)
            ai_estimate_val.configure(text="", text_color=THEME_TEXT_MUTED)
    except Exception:
        ai_goal_val.configure(text="Server unavailable", text_color=THEME_EXPENSE)
        ai_weeks_val.configure(text="Start backend and sync again", text_color=THEME_TEXT_MUTED)
        ai_rates_val.configure(text="", text_color=THEME_TEXT_MUTED)
        ai_target_val.configure(text="", text_color=THEME_TEXT_MUTED)
        ai_estimate_val.configure(text="", text_color=THEME_TEXT_MUTED)

def load_summary():
   try:
       response = requests.get(f"{API_URL}/summary", headers=get_headers())
       if response.status_code == 200:
           data = response.json()
           income, expense, balance = data.get("income", 0), data.get("expense", 0), data.get("balance", 0)
           income_value.configure(text=f"{income:.2f} TL", text_color=THEME_INCOME)
           expense_value.configure(text=f"{expense:.2f} TL", text_color=THEME_EXPENSE)
           balance_value.configure(text=f"{balance:.2f} TL", text_color=THEME_INCOME if balance >= 0 else THEME_EXPENSE)
           balance_card_frame.configure(border_color=THEME_INCOME if balance >= 0 else THEME_EXPENSE)
           transaction_count_value.configure(text=str(len(all_transactions)), text_color=THEME_ACCENT)
   except Exception: pass
 
def load_transactions():
   global all_transactions
   try:
       response = requests.get(f"{API_URL}/transactions", headers=get_headers())
       if response.status_code == 200:
           all_transactions = response.json()
           update_category_breakdown()
           update_transaction_table()
           
           # 👇 GRAFİKLERİN ÇİZİLMESİ İÇİN EKLENMESİ GEREKEN TEK SATIR BU 👇
           update_analytics() 
           
   except Exception: pass
 
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
   widths = [90, 190, 130, 150, 190]
   for title, width in zip(headers, widths):
       ctk.CTkLabel(header, text=title, font=("Arial", 13, "bold"), width=width, text_color=THEME_TEXT_MUTED, anchor="w").pack(side="left", padx=5)
   filtered = get_filtered_transactions()
   if len(filtered) == 0:
       ctk.CTkLabel(transaction_rows_frame, text="No transactions found.", text_color=THEME_TEXT_MUTED, font=("Arial", 14)).pack(pady=35)
       return
   for row in filtered:
       row_frame = ctk.CTkFrame(transaction_rows_frame, fg_color=THEME_BG, corner_radius=10, border_width=1, border_color="#2A2A35")
       row_frame.pack(fill="x", pady=5)
       type_color = THEME_INCOME if row["type"] == "income" else THEME_EXPENSE
       ctk.CTkLabel(row_frame, text=row["type"].upper(), width=90, anchor="w", text_color=type_color, font=("Arial", 13, "bold")).pack(side="left", padx=10, pady=9)
       ctk.CTkLabel(row_frame, text=row["description"], width=190, anchor="w", text_color=THEME_TEXT_MAIN).pack(side="left", padx=5)
       ctk.CTkLabel(row_frame, text=f'{row["amount"]} TL', width=130, anchor="w", text_color=THEME_TEXT_MAIN, font=("Arial", 13, "bold")).pack(side="left", padx=5)
       ctk.CTkLabel(row_frame, text=row["category"], width=150, anchor="w", text_color=THEME_TEXT_MUTED).pack(side="left", padx=5)
       ctk.CTkButton(row_frame, text="Edit", width=75, height=28, fg_color="#34495E", command=lambda r=row: open_edit_transaction(r)).pack(side="left", padx=4)
       ctk.CTkButton(row_frame, text="Delete", width=85, height=28, fg_color="#962D22", command=lambda tid=row["id"]: handle_delete_transaction(tid)).pack(side="left", padx=4)
 
def update_category_breakdown():
   for widget in category_list_frame.winfo_children(): widget.destroy()
   expense_categories = {}
   for transaction in all_transactions:
       if transaction["type"] == "expense":
           category = transaction["category"]
           expense_categories[category] = expense_categories.get(category, 0) + transaction["amount"]
   if len(expense_categories) == 0:
       ctk.CTkLabel(category_list_frame, text="No expense categories yet.", text_color=THEME_TEXT_MUTED).pack(anchor="w", padx=15, pady=10)
       return
   for category, amount in sorted(expense_categories.items(), key=lambda x: x[1], reverse=True)[:5]:
       ctk.CTkLabel(category_list_frame, text=f"• {category}: {amount:.2f} TL", font=("Arial", 14), text_color=THEME_TEXT_MAIN).pack(anchor="w", padx=15, pady=4)
 
def update_analytics():
   for widget in analytics_chart_frame.winfo_children(): widget.destroy()
   income, expense, category_totals = 0, 0, {}
   for transaction in all_transactions:
       amount = transaction["amount"]
       if transaction["type"] == "income": income += amount
       elif transaction["type"] == "expense":
           expense += amount
           category_totals[transaction["category"]] = category_totals.get(transaction["category"], 0) + amount
   balance = income - expense
   analytics_summary.configure(text=f"Income: {income:.2f} TL   |   Expense: {expense:.2f} TL   |   Net Balance: {balance:.2f} TL")
 
   fig1 = Figure(figsize=(4.4, 2.8), dpi=100, facecolor=THEME_CARD)
   ax1 = fig1.add_subplot(111, facecolor=THEME_CARD)
   ax1.bar(["Income", "Expense"], [income, expense], color=[THEME_INCOME, THEME_EXPENSE])
   ax1.tick_params(colors='white')
   fig1.tight_layout()
   FigureCanvasTkAgg(fig1, master=analytics_chart_frame).get_tk_widget().pack(side="left", padx=15, pady=10)
 
   fig2 = Figure(figsize=(4.4, 2.8), dpi=100, facecolor=THEME_CARD)
   ax2 = fig2.add_subplot(111, facecolor=THEME_CARD)
   ax2.tick_params(colors='white')
   if category_totals:
       ax2.bar(list(category_totals.keys()), list(category_totals.values()), color=THEME_ACCENT)
       ax2.tick_params(axis="x", rotation=20, colors='white')
   fig2.tight_layout()
   FigureCanvasTkAgg(fig2, master=analytics_chart_frame).get_tk_widget().pack(side="left", padx=15, pady=10)

def open_live_camera():
    if access_token is None:
        receipt_result_label.configure(text="Please login first.", text_color=THEME_EXPENSE)
        return

    def run_camera():
        global recent_uploaded_files
        receipt_result_label.configure(text="Camera is starting... Press SPACE to capture, ESC to cancel.", text_color=THEME_TEXT_MUTED)
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            receipt_result_label.configure(text="Camera could not be opened.", text_color=THEME_EXPENSE)
            return

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            cv2.imshow("Live Receipt Scanner", frame)
            key = cv2.waitKey(1)
            if key == 32:
                temp_filename = "temp_receipt.jpg"
                cv2.imwrite(temp_filename, frame)
                try:
                    with open(temp_filename, "rb") as file:
                        res = requests.post(
                            f"{API_URL}/upload-receipt",
                            headers=get_headers(),
                            files={"file": ("camera_receipt.jpg", file, "image/jpeg")}
                        )
                    status = "Uploaded / Waiting Analysis" if res.status_code == 200 else "Upload Failed"
                    recent_uploaded_files.insert(0, {"filename": "camera_receipt.jpg", "status": status})
                    receipt_result_label.configure(text=f"camera_receipt.jpg → {status}", text_color=THEME_INCOME if res.status_code == 200 else THEME_EXPENSE)
                    load_all_data_packages()
                    load_uploaded_files()
                except Exception:
                    receipt_result_label.configure(text="Camera upload failed. Check backend.", text_color=THEME_EXPENSE)
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
                break
            elif key == 27:
                break
        cap.release()
        cv2.destroyAllWindows()

    threading.Thread(target=run_camera, daemon=True).start()

def upload_receipt_file():
    global recent_uploaded_files
    if access_token is None:
        receipt_result_label.configure(text="Please login first.", text_color=THEME_EXPENSE)
        return

    file_path = filedialog.askopenfilename(filetypes=[("Receipt Files", "*.jpg *.jpeg *.png *.pdf")])
    if file_path == "":
        return

    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].lower()
    content_type = "application/pdf" if ext == ".pdf" else "image/jpeg"

    try:
        receipt_result_label.configure(text=f"Uploading {filename}...", text_color=THEME_TEXT_MUTED)
        with open(file_path, "rb") as file:
            response = requests.post(
                f"{API_URL}/upload-receipt",
                headers=get_headers(),
                files={"file": (filename, file, content_type)}
            )

        if response.status_code == 200:
            recent_uploaded_files.insert(0, {"filename": filename, "status": "Uploaded / Waiting Analysis"})
            receipt_result_label.configure(text=f"{filename} uploaded. Analysis status is shown below.", text_color=THEME_INCOME)
        else:
            recent_uploaded_files.insert(0, {"filename": filename, "status": "Upload Failed"})
            receipt_result_label.configure(text=f"Upload failed: {response.text}", text_color=THEME_EXPENSE)

        load_all_data_packages()
        load_uploaded_files()
        change_page("ReceiptView", "  🧾  Receipt Upload")
    except Exception:
        recent_uploaded_files.insert(0, {"filename": filename, "status": "Upload Failed"})
        receipt_result_label.configure(text="Upload failed. Check backend connection.", text_color=THEME_EXPENSE)
        load_uploaded_files()

def toggle_receipt_history():
    global show_receipt_history
    show_receipt_history = not show_receipt_history
    load_uploaded_files()

def _add_file_row(parent, filename, status, status_color=None):
    row = ctk.CTkFrame(parent, fg_color=THEME_BG, corner_radius=10, border_width=1, border_color="#2A2A35")
    row.pack(fill="x", pady=5)
    ctk.CTkLabel(row, text=filename, width=360, anchor="w", font=("Arial", 14, "bold")).pack(side="left", padx=10, pady=8)
    ctk.CTkLabel(row, text=status, width=210, anchor="w", text_color=status_color or THEME_TEXT_MUTED).pack(side="left", padx=10)

def load_uploaded_files():
   for widget in uploaded_files_frame.winfo_children():
       widget.destroy()

   ctk.CTkLabel(
       uploaded_files_frame,
       text="Current Upload Status",
       font=("Arial", 16, "bold"),
       text_color=THEME_ACCENT
   ).pack(anchor="w", pady=(0, 8))

   if len(recent_uploaded_files) == 0:
       ctk.CTkLabel(
           uploaded_files_frame,
           text="No file uploaded in this session yet. Upload a receipt to see its live status here.",
           text_color=THEME_TEXT_MUTED
       ).pack(anchor="w", pady=(0, 12))
   else:
       for item in recent_uploaded_files[:5]:
           color = THEME_INCOME if "Failed" not in item["status"] else THEME_EXPENSE
           _add_file_row(uploaded_files_frame, item["filename"], item["status"], color)

   ctk.CTkButton(
       uploaded_files_frame,
       text="Hide Upload History" if show_receipt_history else "Show Previous Uploads",
       width=190,
       height=34,
       fg_color="#2A2A35",
       hover_color="#353545",
       command=toggle_receipt_history
   ).pack(anchor="w", pady=(12, 8))

   if not show_receipt_history:
       return

   ctk.CTkLabel(
       uploaded_files_frame,
       text="Previous Uploaded Files",
       font=("Arial", 16, "bold"),
       text_color=THEME_TEXT_MAIN
   ).pack(anchor="w", pady=(5, 8))

   try:
       response = requests.get(f"{API_URL}/files", headers=get_headers(), timeout=5)
       if response.status_code != 200:
           ctk.CTkLabel(uploaded_files_frame, text="Could not load upload history.", text_color=THEME_EXPENSE).pack(anchor="w")
           return

       files = response.json()
       if len(files) == 0:
           ctk.CTkLabel(uploaded_files_frame, text="No previous uploads found.", text_color=THEME_TEXT_MUTED).pack(anchor="w")
           return

       for file in files:
           status = "Analyzed" if file["is_analyzed"] == 1 else "Waiting Analysis"
           color = THEME_INCOME if file["is_analyzed"] == 1 else THEME_TEXT_MUTED
           _add_file_row(uploaded_files_frame, file["filename"], status, color)
   except Exception:
       ctk.CTkLabel(uploaded_files_frame, text="Server offline. History cannot be loaded.", text_color=THEME_EXPENSE).pack(anchor="w")

def reset_transaction_form():
   global selected_transaction_id
   selected_transaction_id = None
   desc_entry.delete(0, "end")
   amount_entry.delete(0, "end")
   category_entry.delete(0, "end")
 
def open_add_transaction():
   reset_transaction_form()
   show_transaction_screen()
 
def open_edit_transaction(row):
   global selected_transaction_id
   selected_transaction_id = row["id"]
   desc_entry.insert(0, row["description"])
   amount_entry.insert(0, str(row["amount"]))
   category_entry.insert(0, row["category"])
   show_transaction_screen()
 
def handle_save_transaction():
   payload = {"type": transaction_type_option.get(), "description": desc_entry.get(), "amount": float(amount_entry.get()), "category": category_entry.get()}
   try:
       if selected_transaction_id is None: requests.post(f"{API_URL}/transactions", json=payload, headers=get_headers())
       else: requests.put(f"{API_URL}/transactions/{selected_transaction_id}", json=payload, headers=get_headers())
       show_dashboard()
   except Exception: pass
 
def handle_delete_transaction(transaction_id):
   try:
       if requests.delete(f"{API_URL}/transactions/{transaction_id}", headers=get_headers()).status_code == 200: show_dashboard()
   except Exception: pass

# =========================================================================
# 🔐 AUTHENTICATION TABVIEW ENGINE (GİRİŞ EKRANI)
# =========================================================================
auth_tabview = ctk.CTkTabview(app, fg_color="transparent")
auth_tabview.pack(fill="both", expand=True)

auth_tabview.add("LoginView")
auth_tabview.add("RegisterView")

# 🛠️ ÇÖZÜM: CustomTkinter sekmeleri gizlemek için Grid'i kapatır
auth_tabview._segmented_button.grid_forget()

# --- LOGIN GÖVDESİ ---
login_frame = ctk.CTkFrame(auth_tabview.tab("LoginView"), fg_color="transparent")
login_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.7, relheight=0.7)
login_left = ctk.CTkFrame(login_frame, fg_color=THEME_SIDEBAR, corner_radius=20, border_width=1, border_color="#2A2A35")
login_left.pack(side="left", fill="both", expand=True, padx=(0, 10))
ctk.CTkLabel(login_left, text="Finance AI", font=("Arial", 36, "bold"), text_color=THEME_ACCENT).pack(pady=(120, 10))
ctk.CTkLabel(login_left, text="Automated OCR Receipt Scanning\nReal-time FX & Crypto Tracking\nSmart Predictive Analytics", font=("Arial", 14), text_color=THEME_TEXT_MUTED, justify="center").pack(pady=20)
login_right = ctk.CTkFrame(login_frame, fg_color=THEME_CARD, corner_radius=20, border_width=1, border_color="#2A2A35")
login_right.pack(side="right", fill="both", expand=True, padx=(10, 0))
ctk.CTkLabel(login_right, text="Sign In", font=("Arial", 28, "bold")).pack(pady=(70, 30))
login_username_entry = ctk.CTkEntry(login_right, placeholder_text="Username", width=280, height=45, fg_color=THEME_BG, border_color="#2A2A35")
login_username_entry.pack(pady=10)
login_password_entry = ctk.CTkEntry(login_right, placeholder_text="Password", show="*", width=280, height=45, fg_color=THEME_BG, border_color="#2A2A35")
login_password_entry.pack(pady=10)
login_error = ctk.CTkLabel(login_right, text="", text_color=THEME_EXPENSE)
login_error.pack(pady=5)
ctk.CTkButton(login_right, text="Access Dashboard", width=280, height=45, fg_color=THEME_ACCENT, font=("Arial", 14, "bold"), command=handle_login).pack(pady=15)
ctk.CTkButton(login_right, text="Create New Account", width=280, height=35, fg_color="transparent", border_width=1, border_color=THEME_TEXT_MUTED, command=show_register).pack()
 
# --- REGISTER GÖVDESİ ---
register_frame = ctk.CTkFrame(auth_tabview.tab("RegisterView"), fg_color="transparent")
register_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.7, relheight=0.7)
reg_left = ctk.CTkFrame(register_frame, fg_color=THEME_SIDEBAR, corner_radius=20, border_width=1, border_color="#2A2A35")
reg_left.pack(side="left", fill="both", expand=True, padx=(0, 10))
ctk.CTkLabel(reg_left, text="Join Us", font=("Arial", 36, "bold"), text_color=THEME_ACCENT).pack(pady=(140, 10))
reg_right = ctk.CTkFrame(register_frame, fg_color=THEME_CARD, corner_radius=20, border_width=1, border_color="#2A2A35")
reg_right.pack(side="right", fill="both", expand=True, padx=(10, 0))
ctk.CTkLabel(reg_right, text="Register", font=("Arial", 28, "bold")).pack(pady=(50, 20))
reg_username_entry = ctk.CTkEntry(reg_right, placeholder_text="Username", width=280, height=42, fg_color=THEME_BG, border_color="#2A2A35")
reg_username_entry.pack(pady=8)
reg_password_entry = ctk.CTkEntry(reg_right, placeholder_text="Password", show="*", width=280, height=42, fg_color=THEME_BG, border_color="#2A2A35")
reg_password_entry.pack(pady=8)
reg_confirm_entry = ctk.CTkEntry(reg_right, placeholder_text="Confirm Password", show="*", width=280, height=42, fg_color=THEME_BG, border_color="#2A2A35")
reg_confirm_entry.pack(pady=8)
reg_error = ctk.CTkLabel(reg_right, text="", text_color=THEME_EXPENSE)
reg_error.pack(pady=4)
ctk.CTkButton(reg_right, text="Sign Up", width=280, height=42, fg_color=THEME_ACCENT, command=handle_register).pack(pady=10)
ctk.CTkButton(reg_right, text="Back to Login", width=280, height=35, fg_color="transparent", border_width=1, border_color=THEME_TEXT_MUTED, command=show_login).pack()


# =========================================================================
# 🔄 MAIN INTERFACE COMPONENT (KALI-MENÜ & LOGO & USER PANEL)
# =========================================================================
main_layout_frame = ctk.CTkFrame(app, fg_color="transparent")

# --- KALICI SABİT SOL MENÜ (PERSISTENT SIDEBAR) ---
sidebar = ctk.CTkFrame(main_layout_frame, width=250, fg_color=THEME_SIDEBAR, corner_radius=22)
sidebar.pack(side="left", fill="y", padx=(0, 20))
sidebar.pack_propagate(False)

# 💠 VİZYONER LOGO ALANI (BRAND ZONE) - EN ÜSTTE
logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
logo_frame.pack(fill="x", padx=20, pady=(30, 0))
ctk.CTkLabel(logo_frame, text="💠 Finance AI", font=("Arial", 25, "bold"), text_color=THEME_ACCENT, anchor="w").pack(anchor="w")
ctk.CTkLabel(logo_frame, text="Automated Ledger System", font=("Arial", 12), text_color=THEME_TEXT_MUTED, anchor="w").pack(anchor="w", pady=(2, 0))

# 👤 GELİŞTİRİLMİŞ KİŞİSEL BİLGİLER KARTI (USER PRO ZONE)
profile_card = ctk.CTkFrame(sidebar, fg_color="#22222A", height=65, corner_radius=14, border_width=1, border_color="#2A2A35")
profile_card.pack(fill="x", padx=15, pady=(20, 25))
profile_card.pack_propagate(False)

avatar_label = ctk.CTkLabel(profile_card, text="👤", font=("Arial", 20))
avatar_label.pack(side="left", padx=(12, 8))

profile_info_frame = ctk.CTkFrame(profile_card, fg_color="transparent")
profile_info_frame.pack(side="left", fill="y", pady=11)
ctk.CTkLabel(profile_info_frame, text="Active Session", font=("Arial", 10), text_color=THEME_TEXT_MUTED).pack(anchor="w")
user_name_label = ctk.CTkLabel(profile_info_frame, text="TEST USER", font=("Arial", 13, "bold"), text_color=THEME_INCOME)
user_name_label.pack(anchor="w")

# MENÜ NAVİGASYON BUTONLARI
make_sidebar_btn(sidebar, "  📊  Dashboard", show_dashboard).pack(pady=5, padx=15)
make_sidebar_btn(sidebar, "  📈  Analytics", show_analytics).pack(pady=5, padx=15)
make_sidebar_btn(sidebar, "  ➕  Add Transaction", open_add_transaction).pack(pady=5, padx=15)
make_sidebar_btn(sidebar, "  🧾  Receipt Upload", show_receipt_screen).pack(pady=5, padx=15)

# OTURUM KAPATMA
ctk.CTkButton(sidebar, text="🚪 Logout Session", width=220, height=42, fg_color="#2A2A35", hover_color=THEME_EXPENSE, corner_radius=12, font=("Arial", 13, "bold"), command=handle_logout).pack(side="bottom", pady=25)


# --- İÇERİK DEĞİŞTİRME MOTORU (TABS) ---
main_tabview = ctk.CTkTabview(main_layout_frame, fg_color="transparent")
main_tabview.pack(side="right", fill="both", expand=True)

main_tabview.add("DashboardView")
main_tabview.add("AnalyticsView")
main_tabview.add("TransactionFormView")
main_tabview.add("ReceiptView")

# 🛠️ ÇÖZÜM: Ana Ekrandaki sekmeleri de gizlemek için Grid'i kapatır
main_tabview._segmented_button.grid_forget()

# --- PAGE 1: DASHBOARD VIEW ---
dashboard_content = ctk.CTkFrame(main_tabview.tab("DashboardView"), fg_color="transparent")
dashboard_content.pack(fill="both", expand=True)

welcome_label = ctk.CTkLabel(dashboard_content, text="Welcome back", font=("Arial", 32, "bold"))
welcome_label.pack(anchor="w", pady=(5, 2))
ctk.CTkLabel(dashboard_content, text="Here is your financial overview for this month.", font=("Arial", 15), text_color=THEME_TEXT_MUTED).pack(anchor="w", pady=(0, 20))
 
cards_frame = ctk.CTkFrame(dashboard_content, fg_color="transparent")
cards_frame.pack(fill="x", pady=5)
 
def create_card(parent, title, value_text, custom_border="#2A2A35"):
   card = ctk.CTkFrame(parent, width=180, height=115, fg_color=THEME_CARD, corner_radius=18, border_width=1, border_color=custom_border)
   card.pack(side="left", padx=6)
   card.pack_propagate(False)
   ctk.CTkLabel(card, text=title, font=("Arial", 13, "bold"), text_color=THEME_TEXT_MUTED).pack(pady=(20, 5))
   value = ctk.CTkLabel(card, text=value_text, font=("Arial", 21, "bold"))
   value.pack()
   return card, value
 
_, income_value = create_card(cards_frame, "Total Income", "0 TL")
_, expense_value = create_card(cards_frame, "Total Expense", "0 TL")
balance_card_frame, balance_value = create_card(cards_frame, "Net Balance", "0 TL") 
_, risk_value = create_card(cards_frame, "Risk Score", "Low")
_, transaction_count_value = create_card(cards_frame, "Transactions", "0")
 
middle_frame = ctk.CTkFrame(dashboard_content, fg_color="transparent")
middle_frame.pack(fill="x", pady=20)
 
category_card = ctk.CTkFrame(middle_frame, width=300, height=180, fg_color=THEME_CARD, corner_radius=18, border_width=1, border_color="#2A2A35")
category_card.pack(side="left", padx=(0, 15))
category_card.pack_propagate(False)
ctk.CTkLabel(category_card, text="Top Spending Categories", font=("Arial", 16, "bold")).pack(anchor="w", padx=20, pady=(18, 10))
category_list_frame = ctk.CTkFrame(category_card, fg_color="transparent")
category_list_frame.pack(fill="both", expand=True)
 
ai_goal_card = ctk.CTkFrame(middle_frame, width=380, height=250, fg_color=THEME_CARD, corner_radius=18, border_width=1, border_color=THEME_ACCENT)
ai_goal_card.pack(side="left", padx=(0, 15))
ai_goal_card.pack_propagate(False)
ctk.CTkLabel(ai_goal_card, text="🤖 AI Financial Snapshot", font=("Arial", 16, "bold"), text_color=THEME_ACCENT).pack(anchor="w", padx=20, pady=(14, 6))

ai_goal_val = ctk.CTkLabel(ai_goal_card, text="Waiting for finance data...", font=("Arial", 14, "bold"), wraplength=330)
ai_goal_val.pack(anchor="w", padx=20, pady=(2, 2))
ai_weeks_val = ctk.CTkLabel(ai_goal_card, text="USD/TRY: waiting...", font=("Arial", 12), text_color=THEME_TEXT_MUTED, wraplength=330)
ai_weeks_val.pack(anchor="w", padx=20, pady=1)
ai_rates_val = ctk.CTkLabel(ai_goal_card, text="EUR/TRY and GBP/TRY: waiting...", font=("Arial", 12), text_color=THEME_TEXT_MUTED, wraplength=330)
ai_rates_val.pack(anchor="w", padx=20, pady=1)
ai_target_val = ctk.CTkLabel(ai_goal_card, text="Current Target: 1000 USD", font=("Arial", 12, "bold"), text_color=THEME_TEXT_MAIN, wraplength=330)
ai_target_val.pack(anchor="w", padx=20, pady=(5, 1))
ai_estimate_val = ctk.CTkLabel(ai_goal_card, text="Estimated Time: calculating...", font=("Arial", 12, "bold"), text_color=THEME_ACCENT, wraplength=330)
ai_estimate_val.pack(anchor="w", padx=20, pady=(1, 6))

ai_goal_input_frame = ctk.CTkFrame(ai_goal_card, fg_color="transparent")
ai_goal_input_frame.pack(anchor="w", padx=20, pady=(2, 0))
ai_target_entry = ctk.CTkEntry(ai_goal_input_frame, width=95, height=32, placeholder_text="Target", fg_color=THEME_BG, border_color="#2A2A35")
ai_target_entry.insert(0, "1000")
ai_target_entry.pack(side="left", padx=(0, 8))
ai_currency_option = ctk.CTkOptionMenu(ai_goal_input_frame, values=["USD", "EUR", "GBP", "TRY"], width=80, height=32, fg_color="#2A2A35")
ai_currency_option.set("USD")
ai_currency_option.pack(side="left", padx=(0, 8))
ctk.CTkButton(ai_goal_input_frame, text="Set Goal", width=95, height=32, fg_color=THEME_ACCENT, hover_color="#008B90", command=set_ai_goal_from_inputs).pack(side="left")
 
quick_card = ctk.CTkFrame(middle_frame, height=180, fg_color=THEME_CARD, corner_radius=18, border_width=1, border_color="#2A2A35")
quick_card.pack(side="left", fill="both", expand=True)
quick_card.pack_propagate(False)
ctk.CTkLabel(quick_card, text="Quick Actions Panel", font=("Arial", 16, "bold")).pack(anchor="w", padx=20, pady=(18, 12))
quick_buttons = ctk.CTkFrame(quick_card, fg_color="transparent")
quick_buttons.pack(anchor="w", padx=20, pady=5)
ctk.CTkButton(quick_buttons, text="⚡ Add New Record", width=170, height=40, fg_color=THEME_ACCENT, hover_color="#008B90", font=("Arial", 13, "bold"), corner_radius=10, command=open_add_transaction).pack(side="left", padx=(0, 12))
ctk.CTkButton(quick_buttons, text="🔄 Sync Data", width=150, height=40, fg_color="#2A2A35", hover_color="#353545", corner_radius=10, command=load_all_data_packages).pack(side="left")
 
transactions_card = ctk.CTkFrame(dashboard_content, fg_color=THEME_CARD, corner_radius=18, border_width=1, border_color="#2A2A35")
transactions_card.pack(fill="both", expand=True)
table_top = ctk.CTkFrame(transactions_card, fg_color="transparent")
table_top.pack(fill="x", padx=20, pady=(15, 10))
ctk.CTkLabel(table_top, text="Recent Ledger Logs", font=("Arial", 18, "bold")).pack(side="left")
search_entry = ctk.CTkEntry(table_top, placeholder_text="Search logs...", width=220, height=35, fg_color=THEME_BG, border_color="#2A2A35")
search_entry.pack(side="right", padx=(10, 0))
filter_option = ctk.CTkOptionMenu(table_top, values=["All", "income", "expense"], width=110, height=35, fg_color="#2A2A35", command=lambda v: update_transaction_table())
filter_option.pack(side="right")
search_entry.bind("<KeyRelease>", lambda event: update_transaction_table())
transaction_rows_frame = ctk.CTkScrollableFrame(transactions_card, fg_color="transparent", height=190)
transaction_rows_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))


# --- PAGE 2: ANALYTICS VIEW ---
analytics_content = ctk.CTkScrollableFrame(main_tabview.tab("AnalyticsView"), fg_color="transparent")
analytics_content.pack(fill="both", expand=True)

analytics_top_bar = ctk.CTkFrame(analytics_content, fg_color="transparent")
analytics_top_bar.pack(fill="x", pady=(0, 15))
ctk.CTkLabel(analytics_top_bar, text="Financial Intelligence Panel", font=("Arial", 30, "bold")).pack(side="left")
ctk.CTkButton(analytics_top_bar, text="⚡ Back to Dashboard", width=160, height=34, fg_color="#2A2A35", hover_color="#353545", corner_radius=8, font=("Arial", 12, "bold"), command=show_dashboard).pack(side="right")

analytics_card = ctk.CTkFrame(analytics_content, height=100, fg_color=THEME_CARD, corner_radius=18, border_width=1, border_color="#2A2A35")
analytics_card.pack(fill="x", pady=5)
analytics_summary = ctk.CTkLabel(analytics_card, text="Computing...", font=("Arial", 15, "bold"), justify="left")
analytics_summary.pack(anchor="w", padx=25, pady=20)

charts_card = ctk.CTkFrame(analytics_content, fg_color=THEME_CARD, corner_radius=18, border_width=1, border_color="#2A2A35")
charts_card.pack(fill="x", pady=15)
analytics_chart_frame = ctk.CTkFrame(charts_card, fg_color="transparent")
analytics_chart_frame.pack(fill="x", padx=10, pady=10)


# --- PAGE 3: RECEIPT VIEW ---
receipt_content = ctk.CTkScrollableFrame(main_tabview.tab("ReceiptView"), fg_color="transparent")
receipt_content.pack(fill="both", expand=True)

receipt_top_bar = ctk.CTkFrame(receipt_content, fg_color="transparent")
receipt_top_bar.pack(fill="x", pady=(0, 15))
ctk.CTkLabel(receipt_top_bar, text="Computer Vision Receipt OCR", font=("Arial", 30, "bold")).pack(side="left")
ctk.CTkButton(receipt_top_bar, text="⚡ Back to Dashboard", width=160, height=34, fg_color="#2A2A35", hover_color="#353545", corner_radius=8, font=("Arial", 12, "bold"), command=show_dashboard).pack(side="right")

receipt_card = ctk.CTkFrame(receipt_content, fg_color=THEME_CARD, corner_radius=20, border_width=1, border_color="#2A2A35")
receipt_card.pack(fill="both", expand=True, pady=10)

action_box = ctk.CTkFrame(receipt_card, fg_color="transparent")
action_box.pack(fill="x", padx=25, pady=20)
ctk.CTkButton(action_box, text="📂 Choose Local File", width=250, height=42, fg_color=THEME_ACCENT, font=("Arial", 14, "bold"), corner_radius=10, command=upload_receipt_file).pack(side="left", padx=(0, 15))
ctk.CTkButton(action_box, text="📸 Trigger Live Camera Scanner", width=260, height=42, fg_color="#27AE60", font=("Arial", 14, "bold"), corner_radius=10, command=open_live_camera).pack(side="left")

receipt_result_label = ctk.CTkLabel(receipt_card, text="Ready. New uploads will appear in Current Upload Status.", font=("Arial", 13), text_color=THEME_TEXT_MUTED)
receipt_result_label.pack(anchor="w", padx=25, pady=(0, 15))

uploaded_files_frame = ctk.CTkFrame(receipt_card, fg_color="transparent")
uploaded_files_frame.pack(fill="both", expand=True, padx=25, pady=15)


# --- PAGE 4: TRANSACTION FORM VIEW ---
transaction_content = ctk.CTkFrame(main_tabview.tab("TransactionFormView"), fg_color="transparent")
transaction_content.pack(fill="both", expand=True)

form_top_bar = ctk.CTkFrame(transaction_content, fg_color="transparent")
form_top_bar.pack(fill="x", pady=(0, 15))
ctk.CTkLabel(form_top_bar, text="Ledger Registry", font=("Arial", 30, "bold")).pack(side="left")
ctk.CTkButton(form_top_bar, text="⚡ Back to Dashboard", width=160, height=34, fg_color="#2A2A35", hover_color="#353545", corner_radius=8, font=("Arial", 12, "bold"), command=show_dashboard).pack(side="right")

transaction_frame = ctk.CTkFrame(transaction_content, width=480, height=480, fg_color=THEME_SIDEBAR, corner_radius=25, border_width=1, border_color="#2A2A35")
transaction_frame.place(relx=0.5, rely=0.5, anchor="center")

ctk.CTkLabel(transaction_frame, text="Transaction Details", font=("Arial", 22, "bold")).pack(pady=(30, 15))
transaction_type_option = ctk.CTkOptionMenu(transaction_frame, values=["income", "expense"], width=340, height=42)
transaction_type_option.pack(pady=10)
desc_entry = ctk.CTkEntry(transaction_frame, placeholder_text="Transaction Details (e.g. Market)", width=340, height=42, fg_color=THEME_BG, border_color="#2A2A35")
desc_entry.pack(pady=10)
amount_entry = ctk.CTkEntry(transaction_frame, placeholder_text="Volume (Amount in TL)", width=340, height=42, fg_color=THEME_BG, border_color="#2A2A35")
amount_entry.pack(pady=10)
category_entry = ctk.CTkEntry(transaction_frame, placeholder_text="Classification Group (Category)", width=340, height=42, fg_color=THEME_BG, border_color="#2A2A35")
category_entry.pack(pady=10)
save_transaction_button = ctk.CTkButton(transaction_frame, text="Commit Entry", width=340, height=45, fg_color=THEME_ACCENT, font=("Arial", 14, "bold"), corner_radius=10, command=handle_save_transaction)
save_transaction_button.pack(pady=20)


# =========================================================================
# 🚀 Geliştirme Ortamı Başlangıç Ayarı
# =========================================================================
# Sistem ilk açılışta temiz asimetrik giriş ekranıyla başlar.
show_login()

app.mainloop()