import glob
import customtkinter as ctk
import requests
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from receipt_ai import process_receipt

API_URL = "http://127.0.0.1:8000"

access_token = None
current_username = ""
selected_transaction_id = None
all_transactions = []

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.geometry("1350x800")
app.title("Personal Financial Assistant")


def get_headers():
    return {"Authorization": f"Bearer {access_token}"}


def show_error(label, message):
    label.configure(text=message, text_color="red")


def clear_frames():
    login_frame.place_forget()
    register_frame.place_forget()
    dashboard_frame.place_forget()
    transaction_frame.place_forget()
    analytics_frame.place_forget()
    receipt_frame.place_forget()


def show_login():
    clear_frames()
    login_frame.place(relx=0.5, rely=0.5, anchor="center")


def show_register():
    clear_frames()
    register_frame.place(relx=0.5, rely=0.5, anchor="center")


def show_dashboard():
    clear_frames()
    welcome_label.configure(text=f"Welcome back, {current_username}")
    load_summary()
    load_transactions()
    dashboard_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.94, relheight=0.9)


def show_analytics():
    clear_frames()
    load_transactions()
    update_analytics()
    analytics_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.94, relheight=0.9)


def show_transaction_screen():
    clear_frames()
    transaction_frame.place(relx=0.5, rely=0.5, anchor="center")


def show_receipt_screen():
    clear_frames()
    receipt_result_label.configure(text="Click the button to scan all receipt images.", text_color="white")
    receipt_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.82, relheight=0.82)


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
        response = requests.post(
            f"{API_URL}/register",
            json={"username": username, "password": password}
        )

        if response.status_code == 200:
            reg_error.configure(text="Account created successfully", text_color="lightgreen")
            show_login()
        else:
            show_error(reg_error, response.json().get("detail", "Register failed"))

    except requests.exceptions.ConnectionError:
        show_error(reg_error, "Backend server is not running")


def handle_login():
    global access_token, current_username

    username = login_username_entry.get()
    password = login_password_entry.get()

    if username == "" or password == "":
        show_error(login_error, "Please fill all fields")
        return

    try:
        response = requests.post(
            f"{API_URL}/login",
            json={"username": username, "password": password}
        )

        if response.status_code == 200:
            access_token = response.json()["access_token"]
            current_username = username
            login_error.configure(text="")
            show_dashboard()
        else:
            show_error(login_error, response.json().get("detail", "Login failed"))

    except requests.exceptions.ConnectionError:
        show_error(login_error, "Backend server is not running")


def handle_logout():
    global access_token, current_username
    access_token = None
    current_username = ""
    show_login()


def load_summary():
    try:
        response = requests.get(f"{API_URL}/summary", headers=get_headers())

        if response.status_code == 200:
            data = response.json()

            income = data.get("income", 0)
            expense = data.get("expense", 0)
            balance = data.get("balance", 0)

            income_value.configure(text=f"{income:.2f} TL")
            expense_value.configure(text=f"{expense:.2f} TL")
            balance_value.configure(text=f"{balance:.2f} TL")

            ratio = expense / income if income > 0 else 0

            if ratio > 0.7:
                risk_value.configure(text="High")
                risk_status_label.configure(text="High Risk")
                risk_progress.set(0.9)
            elif ratio > 0.4:
                risk_value.configure(text="Medium")
                risk_status_label.configure(text="Medium Risk")
                risk_progress.set(0.55)
            else:
                risk_value.configure(text="Low")
                risk_status_label.configure(text="Low Risk")
                risk_progress.set(0.25)

            ratio_label.configure(text=f"Expense / Income Ratio: {ratio:.2f}")

    except requests.exceptions.ConnectionError:
        income_value.configure(text="Error")
        expense_value.configure(text="Error")
        balance_value.configure(text="Error")
        risk_value.configure(text="Error")


def load_transactions():
    global all_transactions

    try:
        response = requests.get(f"{API_URL}/transactions", headers=get_headers())

        if response.status_code == 200:
            all_transactions = response.json()
            transaction_count_value.configure(text=str(len(all_transactions)))
            update_category_breakdown()
            update_transaction_table()
        else:
            all_transactions = []
            update_transaction_table()

    except requests.exceptions.ConnectionError:
        all_transactions = []
        update_transaction_table()


def get_filtered_transactions():
    search_text = search_entry.get().lower()
    filter_value = filter_option.get()

    filtered = all_transactions

    if filter_value != "All":
        filtered = [t for t in filtered if t["type"] == filter_value.lower()]

    if search_text != "":
        filtered = [
            t for t in filtered
            if search_text in t["description"].lower()
            or search_text in t["category"].lower()
        ]

    return filtered


def update_transaction_table():
    for widget in transaction_rows_frame.winfo_children():
        widget.destroy()

    header = ctk.CTkFrame(transaction_rows_frame, fg_color="transparent")
    header.pack(fill="x", pady=(0, 8))

    headers = ["Type", "Description", "Amount", "Category", "Actions"]
    widths = [90, 190, 130, 150, 190]

    for title, width in zip(headers, widths):
        ctk.CTkLabel(
            header,
            text=title,
            font=("Arial", 13, "bold"),
            width=width,
            anchor="w"
        ).pack(side="left", padx=5)

    filtered = get_filtered_transactions()

    if len(filtered) == 0:
        ctk.CTkLabel(
            transaction_rows_frame,
            text="No transactions found.\nTry adding a transaction or changing the filter.",
            text_color="gray",
            font=("Arial", 14)
        ).pack(pady=35)
        return

    for row in filtered:
        row_frame = ctk.CTkFrame(transaction_rows_frame, corner_radius=10)
        row_frame.pack(fill="x", pady=5)

        type_text = row["type"]
        type_color = "lightgreen" if type_text == "income" else "#ff7777"

        ctk.CTkLabel(
            row_frame,
            text=type_text.upper(),
            width=90,
            anchor="w",
            text_color=type_color,
            font=("Arial", 13, "bold")
        ).pack(side="left", padx=5, pady=9)

        ctk.CTkLabel(row_frame, text=row["description"], width=190, anchor="w").pack(side="left", padx=5)
        ctk.CTkLabel(row_frame, text=f'{row["amount"]} TL', width=130, anchor="w").pack(side="left", padx=5)
        ctk.CTkLabel(row_frame, text=row["category"], width=150, anchor="w").pack(side="left", padx=5)

        ctk.CTkButton(
            row_frame,
            text="Edit",
            width=75,
            height=28,
            command=lambda r=row: open_edit_transaction(r)
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            row_frame,
            text="Delete",
            width=85,
            height=28,
            fg_color="darkred",
            hover_color="red",
            command=lambda tid=row["id"]: handle_delete_transaction(tid)
        ).pack(side="left", padx=4)


def update_category_breakdown():
    for widget in category_list_frame.winfo_children():
        widget.destroy()

    expense_categories = {}

    for transaction in all_transactions:
        if transaction["type"] == "expense":
            category = transaction["category"]
            expense_categories[category] = expense_categories.get(category, 0) + transaction["amount"]

    if len(expense_categories) == 0:
        ctk.CTkLabel(
            category_list_frame,
            text="No expense categories yet.",
            text_color="gray"
        ).pack(anchor="w", padx=15, pady=10)
        return

    sorted_categories = sorted(expense_categories.items(), key=lambda x: x[1], reverse=True)

    for category, amount in sorted_categories[:5]:
        ctk.CTkLabel(
            category_list_frame,
            text=f"{category}: {amount:.2f} TL",
            font=("Arial", 14),
            anchor="w"
        ).pack(anchor="w", padx=15, pady=4)


def update_analytics():
    for widget in analytics_chart_frame.winfo_children():
        widget.destroy()

    for widget in analytics_category_table.winfo_children():
        widget.destroy()

    income = 0
    expense = 0
    category_totals = {}

    for t in all_transactions:
        amount = t["amount"]

        if t["type"] == "income":
            income += amount
        elif t["type"] == "expense":
            expense += amount
            category = t["category"]
            category_totals[category] = category_totals.get(category, 0) + amount

    balance = income - expense
    ratio = expense / income if income > 0 else 0

    analytics_summary.configure(
        text=f"Income: {income:.2f} TL\n"
             f"Expense: {expense:.2f} TL\n"
             f"Balance: {balance:.2f} TL\n"
             f"Expense Ratio: {ratio:.2f}"
    )

    if ratio > 0.7:
        risk_text = "High"
        insight = "Your expenses are high compared to your income. You should reduce unnecessary spending."
        progress_value = 0.9
    elif ratio > 0.4:
        risk_text = "Medium"
        insight = "Your spending is moderate. You should monitor your fixed expenses."
        progress_value = 0.55
    else:
        risk_text = "Low"
        insight = "Your financial situation looks healthy. Your expenses are low compared to income."
        progress_value = 0.25

    analytics_risk.configure(text=f"Risk Level: {risk_text}")
    analytics_progress.set(progress_value)
    insight_label.configure(text=insight)

    fig1 = Figure(figsize=(4.2, 2.6), dpi=100)
    ax1 = fig1.add_subplot(111)
    ax1.bar(["Income", "Expense"], [income, expense])
    ax1.set_title("Income vs Expense")
    ax1.set_ylabel("Amount (TL)")
    fig1.tight_layout()

    canvas1 = FigureCanvasTkAgg(fig1, master=analytics_chart_frame)
    canvas1.draw()
    canvas1.get_tk_widget().pack(side="left", padx=10, pady=10)

    fig2 = Figure(figsize=(4.2, 2.6), dpi=100)
    ax2 = fig2.add_subplot(111)

    if category_totals:
        categories = list(category_totals.keys())
        amounts = list(category_totals.values())
        ax2.bar(categories, amounts)
        ax2.set_title("Expenses by Category")
        ax2.set_ylabel("Amount (TL)")
        ax2.tick_params(axis="x", rotation=25)
    else:
        ax2.text(0.5, 0.5, "No expense data", ha="center", va="center")
        ax2.set_axis_off()

    fig2.tight_layout()

    canvas2 = FigureCanvasTkAgg(fig2, master=analytics_chart_frame)
    canvas2.draw()
    canvas2.get_tk_widget().pack(side="left", padx=10, pady=10)

    ctk.CTkLabel(
        analytics_category_table,
        text="Category",
        font=("Arial", 14, "bold"),
        width=180,
        anchor="w"
    ).grid(row=0, column=0, padx=10, pady=5)

    ctk.CTkLabel(
        analytics_category_table,
        text="Amount",
        font=("Arial", 14, "bold"),
        width=120,
        anchor="w"
    ).grid(row=0, column=1, padx=10, pady=5)

    sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)

    if not sorted_categories:
        ctk.CTkLabel(
            analytics_category_table,
            text="No category data available.",
            text_color="gray"
        ).grid(row=1, column=0, padx=10, pady=10)
    else:
        for index, (category, amount) in enumerate(sorted_categories, start=1):
            ctk.CTkLabel(
                analytics_category_table,
                text=category,
                width=180,
                anchor="w"
            ).grid(row=index, column=0, padx=10, pady=4)

            ctk.CTkLabel(
                analytics_category_table,
                text=f"{amount:.2f} TL",
                width=120,
                anchor="w"
            ).grid(row=index, column=1, padx=10, pady=4)


def scan_receipts_and_add():
    if access_token is None:
        receipt_result_label.configure(text="Please login first.", text_color="red")
        return

    receipt_result_label.configure(text="Scanning receipts... Please wait.", text_color="white")
    app.update()

    receipt_files = glob.glob("*.jpg") + glob.glob("*.jpeg") + glob.glob("*.png")

    if not receipt_files:
        receipt_result_label.configure(text="No receipt images found in project folder.", text_color="red")
        return

    added_count = 0
    result_text = ""

    for file in receipt_files:
        store, total, category = process_receipt(file)

        result_text += f"{file}\n{store} | {category} | {total} TL\n\n"

        if total > 0:
            try:
                response = requests.post(
                    f"{API_URL}/transactions",
                    headers=get_headers(),
                    json={
                        "type": "expense",
                        "description": store,
                        "amount": total,
                        "category": category
                    }
                )

                if response.status_code == 200:
                    added_count += 1
                else:
                    result_text += f"Could not add: {response.text}\n\n"

            except requests.exceptions.ConnectionError:
                receipt_result_label.configure(text="Backend server is not running.", text_color="red")
                return

    result_text += f"\nAdded Transactions: {added_count}"
    receipt_result_label.configure(text=result_text, text_color="white")


def reset_transaction_form():
    global selected_transaction_id

    selected_transaction_id = None
    transaction_type_option.set("expense")
    desc_entry.delete(0, "end")
    amount_entry.delete(0, "end")
    category_entry.delete(0, "end")
    transaction_error.configure(text="")
    save_transaction_button.configure(text="Save Transaction")


def open_add_transaction():
    reset_transaction_form()
    show_transaction_screen()


def open_edit_transaction(row):
    global selected_transaction_id

    selected_transaction_id = row["id"]

    transaction_type_option.set(row["type"])
    desc_entry.delete(0, "end")
    desc_entry.insert(0, row["description"])

    amount_entry.delete(0, "end")
    amount_entry.insert(0, str(row["amount"]))

    category_entry.delete(0, "end")
    category_entry.insert(0, row["category"])

    save_transaction_button.configure(text="Update Transaction")
    show_transaction_screen()


def handle_save_transaction():
    global selected_transaction_id

    t_type = transaction_type_option.get()
    description = desc_entry.get()
    amount = amount_entry.get()
    category = category_entry.get()

    if description == "" or amount == "" or category == "":
        show_error(transaction_error, "Please fill all fields")
        return

    try:
        amount = float(amount)
    except ValueError:
        show_error(transaction_error, "Amount must be a number")
        return

    payload = {
        "type": t_type,
        "description": description,
        "amount": amount,
        "category": category
    }

    try:
        if selected_transaction_id is None:
            response = requests.post(
                f"{API_URL}/transactions",
                json=payload,
                headers=get_headers()
            )
        else:
            response = requests.put(
                f"{API_URL}/transactions/{selected_transaction_id}",
                json=payload,
                headers=get_headers()
            )

        if response.status_code == 200:
            reset_transaction_form()
            show_dashboard()
        else:
            show_error(transaction_error, "Transaction failed")

    except requests.exceptions.ConnectionError:
        show_error(transaction_error, "Backend server is not running")


def handle_delete_transaction(transaction_id):
    try:
        response = requests.delete(
            f"{API_URL}/transactions/{transaction_id}",
            headers=get_headers()
        )

        if response.status_code == 200:
            show_dashboard()

    except requests.exceptions.ConnectionError:
        pass


# LOGIN FRAME
login_frame = ctk.CTkFrame(app, width=430, height=430, corner_radius=22)
login_frame.pack_propagate(False)

ctk.CTkLabel(login_frame, text="Personal Financial Assistant", font=("Arial", 26, "bold")).pack(pady=(40, 10))
ctk.CTkLabel(login_frame, text="Login to view your financial dashboard", font=("Arial", 14), text_color="gray").pack(pady=(0, 25))

login_username_entry = ctk.CTkEntry(login_frame, placeholder_text="Username", width=310, height=42)
login_username_entry.pack(pady=10)

login_password_entry = ctk.CTkEntry(login_frame, placeholder_text="Password", show="*", width=310, height=42)
login_password_entry.pack(pady=10)

login_error = ctk.CTkLabel(login_frame, text="", text_color="red")
login_error.pack(pady=5)

ctk.CTkButton(login_frame, text="Login", width=310, height=42, command=handle_login).pack(pady=10)
ctk.CTkButton(login_frame, text="Create Account", width=310, height=36, fg_color="transparent", border_width=1, command=show_register).pack(pady=10)


# REGISTER FRAME
register_frame = ctk.CTkFrame(app, width=430, height=470, corner_radius=22)
register_frame.pack_propagate(False)

ctk.CTkLabel(register_frame, text="Create Account", font=("Arial", 26, "bold")).pack(pady=(38, 10))
ctk.CTkLabel(register_frame, text="Register to start tracking your finances", font=("Arial", 14), text_color="gray").pack(pady=(0, 25))

reg_username_entry = ctk.CTkEntry(register_frame, placeholder_text="Username", width=310, height=42)
reg_username_entry.pack(pady=10)

reg_password_entry = ctk.CTkEntry(register_frame, placeholder_text="Password", show="*", width=310, height=42)
reg_password_entry.pack(pady=10)

reg_confirm_entry = ctk.CTkEntry(register_frame, placeholder_text="Confirm Password", show="*", width=310, height=42)
reg_confirm_entry.pack(pady=10)

reg_error = ctk.CTkLabel(register_frame, text="", text_color="red")
reg_error.pack(pady=5)

ctk.CTkButton(register_frame, text="Register", width=310, height=42, command=handle_register).pack(pady=10)
ctk.CTkButton(register_frame, text="Back to Login", width=310, height=36, fg_color="transparent", border_width=1, command=show_login).pack(pady=10)


# DASHBOARD FRAME
dashboard_frame = ctk.CTkFrame(app, corner_radius=18)

sidebar = ctk.CTkFrame(dashboard_frame, width=230, corner_radius=18)
sidebar.pack(side="left", fill="y", padx=(0, 15))
sidebar.pack_propagate(False)

ctk.CTkLabel(sidebar, text="Finance App", font=("Arial", 24, "bold")).pack(pady=(35, 10))
ctk.CTkLabel(sidebar, text="Personal Assistant", font=("Arial", 13), text_color="gray").pack(pady=(0, 30))

ctk.CTkButton(sidebar, text="Dashboard", width=180, height=40, command=show_dashboard).pack(pady=10)
ctk.CTkButton(sidebar, text="Analytics", width=180, height=40, command=show_analytics).pack(pady=10)
ctk.CTkButton(sidebar, text="Add Transaction", width=180, height=40, command=open_add_transaction).pack(pady=10)
ctk.CTkButton(sidebar, text="Receipt Scanner", width=180, height=40, command=show_receipt_screen).pack(pady=10)
ctk.CTkButton(sidebar, text="Logout", width=180, height=40, fg_color="gray", command=handle_logout).pack(side="bottom", pady=35)

content = ctk.CTkFrame(dashboard_frame, fg_color="transparent")
content.pack(side="right", fill="both", expand=True, padx=25, pady=25)

welcome_label = ctk.CTkLabel(content, text="Welcome back", font=("Arial", 30, "bold"))
welcome_label.pack(anchor="w", pady=(5, 5))

ctk.CTkLabel(content, text="Here is your financial overview for this month.", font=("Arial", 15), text_color="gray").pack(anchor="w", pady=(0, 20))

cards_frame = ctk.CTkFrame(content, fg_color="transparent")
cards_frame.pack(fill="x", pady=10)


def create_card(parent, title, value_text):
    card = ctk.CTkFrame(parent, width=170, height=105, corner_radius=18)
    card.pack(side="left", padx=7)
    card.pack_propagate(False)

    ctk.CTkLabel(card, text=title, font=("Arial", 13), text_color="gray").pack(pady=(16, 8))
    value = ctk.CTkLabel(card, text=value_text, font=("Arial", 20, "bold"))
    value.pack()

    return value


income_value = create_card(cards_frame, "Total Income", "0 TL")
expense_value = create_card(cards_frame, "Total Expense", "0 TL")
balance_value = create_card(cards_frame, "Balance", "0 TL")
risk_value = create_card(cards_frame, "Risk Score", "Low")
transaction_count_value = create_card(cards_frame, "Transactions", "0")

middle_frame = ctk.CTkFrame(content, fg_color="transparent")
middle_frame.pack(fill="x", pady=20)

category_card = ctk.CTkFrame(middle_frame, width=280, height=165, corner_radius=18)
category_card.pack(side="left", padx=(0, 15))
category_card.pack_propagate(False)

ctk.CTkLabel(category_card, text="Top Spending Categories", font=("Arial", 17, "bold")).pack(anchor="w", padx=15, pady=(15, 8))

category_list_frame = ctk.CTkFrame(category_card, fg_color="transparent")
category_list_frame.pack(fill="both", expand=True)

risk_card = ctk.CTkFrame(middle_frame, width=260, height=165, corner_radius=18)
risk_card.pack(side="left", padx=(0, 15))
risk_card.pack_propagate(False)

ctk.CTkLabel(risk_card, text="Risk Level", font=("Arial", 17, "bold")).pack(anchor="w", padx=15, pady=(15, 8))

risk_status_label = ctk.CTkLabel(risk_card, text="Low Risk", font=("Arial", 18, "bold"))
risk_status_label.pack(pady=(5, 8))

risk_progress = ctk.CTkProgressBar(risk_card, width=210)
risk_progress.pack(pady=5)
risk_progress.set(0.25)

ratio_label = ctk.CTkLabel(risk_card, text="Expense / Income Ratio: 0.00", font=("Arial", 12), text_color="gray")
ratio_label.pack(pady=5)

quick_card = ctk.CTkFrame(middle_frame, height=165, corner_radius=18)
quick_card.pack(side="left", fill="both", expand=True)
quick_card.pack_propagate(False)

ctk.CTkLabel(quick_card, text="Quick Actions", font=("Arial", 17, "bold")).pack(anchor="w", padx=20, pady=(18, 8))

quick_buttons = ctk.CTkFrame(quick_card, fg_color="transparent")
quick_buttons.pack(anchor="w", padx=20, pady=(10, 0))

ctk.CTkButton(quick_buttons, text="Add Income / Expense", width=180, height=38, command=open_add_transaction).pack(side="left", padx=(0, 12))
ctk.CTkButton(quick_buttons, text="Refresh Dashboard", width=180, height=38, fg_color="gray", command=show_dashboard).pack(side="left")

transactions_card = ctk.CTkFrame(content, corner_radius=18)
transactions_card.pack(fill="both", expand=True)

table_top = ctk.CTkFrame(transactions_card, fg_color="transparent")
table_top.pack(fill="x", padx=20, pady=(18, 10))

ctk.CTkLabel(table_top, text="Recent Transactions", font=("Arial", 20, "bold")).pack(side="left")

search_entry = ctk.CTkEntry(table_top, placeholder_text="Search transactions...", width=210, height=35)
search_entry.pack(side="right", padx=(10, 0))

filter_option = ctk.CTkOptionMenu(table_top, values=["All", "income", "expense"], width=120, height=35, command=lambda value: update_transaction_table())
filter_option.pack(side="right")

search_entry.bind("<KeyRelease>", lambda event: update_transaction_table())

transaction_rows_frame = ctk.CTkScrollableFrame(transactions_card, fg_color="transparent", height=240)
transaction_rows_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))


# ANALYTICS FRAME
analytics_frame = ctk.CTkFrame(app, corner_radius=18)

analytics_sidebar = ctk.CTkFrame(analytics_frame, width=230, corner_radius=18)
analytics_sidebar.pack(side="left", fill="y", padx=(0, 15))
analytics_sidebar.pack_propagate(False)

ctk.CTkLabel(analytics_sidebar, text="Finance App", font=("Arial", 24, "bold")).pack(pady=(35, 10))
ctk.CTkLabel(analytics_sidebar, text="Analytics Panel", font=("Arial", 13), text_color="gray").pack(pady=(0, 30))

ctk.CTkButton(analytics_sidebar, text="Dashboard", width=180, height=40, command=show_dashboard).pack(pady=10)
ctk.CTkButton(analytics_sidebar, text="Analytics", width=180, height=40, command=show_analytics).pack(pady=10)
ctk.CTkButton(analytics_sidebar, text="Add Transaction", width=180, height=40, command=open_add_transaction).pack(pady=10)
ctk.CTkButton(analytics_sidebar, text="Receipt Scanner", width=180, height=40, command=show_receipt_screen).pack(pady=10)
ctk.CTkButton(analytics_sidebar, text="Logout", width=180, height=40, fg_color="gray", command=handle_logout).pack(side="bottom", pady=35)

analytics_content = ctk.CTkScrollableFrame(analytics_frame, fg_color="transparent")
analytics_content.pack(side="right", fill="both", expand=True, padx=30, pady=30)

ctk.CTkLabel(analytics_content, text="Financial Analytics", font=("Arial", 32, "bold")).pack(anchor="w", pady=(0, 8))
ctk.CTkLabel(analytics_content, text="Detailed overview of income, expenses, categories, and financial risk.", font=("Arial", 15), text_color="gray").pack(anchor="w", pady=(0, 25))

top_analytics_frame = ctk.CTkFrame(analytics_content, fg_color="transparent")
top_analytics_frame.pack(fill="x", pady=10)

analytics_card = ctk.CTkFrame(top_analytics_frame, width=420, height=250, corner_radius=18)
analytics_card.pack(side="left", padx=(0, 20))
analytics_card.pack_propagate(False)

ctk.CTkLabel(analytics_card, text="Current Financial Overview", font=("Arial", 21, "bold")).pack(anchor="w", padx=25, pady=(25, 12))

analytics_summary = ctk.CTkLabel(analytics_card, text="Income: 0 TL\nExpense: 0 TL\nBalance: 0 TL\nExpense Ratio: 0.00", font=("Arial", 16), justify="left")
analytics_summary.pack(anchor="w", padx=25, pady=8)

analytics_risk = ctk.CTkLabel(analytics_card, text="Risk Level: Low", font=("Arial", 18, "bold"))
analytics_risk.pack(anchor="w", padx=25, pady=(10, 5))

analytics_progress = ctk.CTkProgressBar(analytics_card, width=350)
analytics_progress.pack(anchor="w", padx=25, pady=8)
analytics_progress.set(0.25)

insight_card = ctk.CTkFrame(top_analytics_frame, width=500, height=250, corner_radius=18)
insight_card.pack(side="left", fill="both", expand=True)
insight_card.pack_propagate(False)

ctk.CTkLabel(insight_card, text="Financial Insight", font=("Arial", 21, "bold")).pack(anchor="w", padx=25, pady=(25, 12))

insight_label = ctk.CTkLabel(insight_card, text="Your financial insight will appear here.", font=("Arial", 16), wraplength=430, justify="left")
insight_label.pack(anchor="w", padx=25, pady=10)

ctk.CTkLabel(insight_card, text="Future AI Recommendation", font=("Arial", 17, "bold")).pack(anchor="w", padx=25, pady=(20, 5))

ctk.CTkLabel(
    insight_card,
    text="Personalized savings recommendations will be integrated here.",
    font=("Arial", 14),
    text_color="gray",
    wraplength=430,
    justify="left"
).pack(anchor="w", padx=25)

charts_card = ctk.CTkFrame(analytics_content, corner_radius=18)
charts_card.pack(fill="x", pady=20)

ctk.CTkLabel(charts_card, text="Visual Reports", font=("Arial", 22, "bold")).pack(anchor="w", padx=25, pady=(20, 10))

analytics_chart_frame = ctk.CTkFrame(charts_card, fg_color="transparent")
analytics_chart_frame.pack(fill="x", padx=20, pady=(0, 20))

bottom_analytics_frame = ctk.CTkFrame(analytics_content, fg_color="transparent")
bottom_analytics_frame.pack(fill="x", pady=(0, 20))

category_table_card = ctk.CTkFrame(bottom_analytics_frame, width=430, height=260, corner_radius=18)
category_table_card.pack(side="left", padx=(0, 20))
category_table_card.pack_propagate(False)

ctk.CTkLabel(category_table_card, text="Top Expense Categories", font=("Arial", 21, "bold")).pack(anchor="w", padx=25, pady=(20, 10))

analytics_category_table = ctk.CTkFrame(category_table_card, fg_color="transparent")
analytics_category_table.pack(anchor="w", padx=15, pady=5)

future_ai_card = ctk.CTkFrame(bottom_analytics_frame, width=500, height=260, corner_radius=18)
future_ai_card.pack(side="left", fill="both", expand=True)
future_ai_card.pack_propagate(False)

ctk.CTkLabel(future_ai_card, text="Future AI Modules", font=("Arial", 21, "bold")).pack(anchor="w", padx=25, pady=(20, 10))

ctk.CTkLabel(
    future_ai_card,
    text="- NLP-based expense categorization\n"
         "- Time-series expense prediction\n"
         "- Personalized savings recommendations\n"
         "- Monthly financial risk forecasting",
    font=("Arial", 16),
    justify="left"
).pack(anchor="w", padx=25, pady=10)


# RECEIPT FRAME
receipt_frame = ctk.CTkFrame(app, corner_radius=18)

receipt_content = ctk.CTkScrollableFrame(receipt_frame, fg_color="transparent")
receipt_content.pack(fill="both", expand=True, padx=35, pady=35)

ctk.CTkLabel(
    receipt_content,
    text="Receipt AI Scanner",
    font=("Arial", 32, "bold")
).pack(anchor="w", pady=(0, 10))

ctk.CTkLabel(
    receipt_content,
    text="This screen scans all receipt images in the project folder and automatically adds them as expense transactions.",
    font=("Arial", 15),
    text_color="gray",
    wraplength=850
).pack(anchor="w", pady=(0, 25))

ctk.CTkButton(
    receipt_content,
    text="Scan All Receipts and Add to System",
    width=360,
    height=45,
    command=scan_receipts_and_add
).pack(anchor="w", pady=15)

receipt_result_label = ctk.CTkLabel(
    receipt_content,
    text="Click the button to scan all receipt images.",
    font=("Arial", 15),
    justify="left",
    wraplength=900
)
receipt_result_label.pack(anchor="w", pady=20)

ctk.CTkButton(
    receipt_content,
    text="Back to Dashboard",
    width=300,
    height=40,
    fg_color="gray",
    command=show_dashboard
).pack(anchor="w", pady=20)


# TRANSACTION FRAME
transaction_frame = ctk.CTkFrame(app, width=500, height=530, corner_radius=22)
transaction_frame.pack_propagate(False)

ctk.CTkLabel(transaction_frame, text="Add / Edit Transaction", font=("Arial", 28, "bold")).pack(pady=(35, 10))
ctk.CTkLabel(transaction_frame, text="Add or update an income/expense record", font=("Arial", 14), text_color="gray").pack(pady=(0, 20))

transaction_type_option = ctk.CTkOptionMenu(transaction_frame, values=["income", "expense"], width=320, height=42)
transaction_type_option.pack(pady=10)
transaction_type_option.set("expense")

desc_entry = ctk.CTkEntry(transaction_frame, placeholder_text="Description", width=320, height=42)
desc_entry.pack(pady=10)

amount_entry = ctk.CTkEntry(transaction_frame, placeholder_text="Amount", width=320, height=42)
amount_entry.pack(pady=10)

category_entry = ctk.CTkEntry(transaction_frame, placeholder_text="Category", width=320, height=42)
category_entry.pack(pady=10)

transaction_error = ctk.CTkLabel(transaction_frame, text="", text_color="red")
transaction_error.pack(pady=5)

save_transaction_button = ctk.CTkButton(transaction_frame, text="Save Transaction", width=320, height=42, command=handle_save_transaction)
save_transaction_button.pack(pady=10)

ctk.CTkButton(transaction_frame, text="Back to Dashboard", width=320, height=38, fg_color="transparent", border_width=1, command=show_dashboard).pack(pady=10)


show_login()
app.mainloop()