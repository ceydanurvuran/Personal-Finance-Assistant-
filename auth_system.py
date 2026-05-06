import pandas as pd
import os

FILE = "users.csv"

# =========================
# DOSYA OLUŞTURMA
# =========================
def init_file():
    if not os.path.exists(FILE):
        df = pd.DataFrame(columns=["id", "username", "password", "monthly_income"])
        df.to_csv(FILE, index=False)


# =========================
# REGISTER
# =========================
def register(username, password, monthly_income):
    df = pd.read_csv(FILE)

    # kullanıcı kontrolü
    if username in df["username"].values:
        print("User already exists ❌")
        return

    new_id = 1 if df.empty else df["id"].max() + 1

    new_user = pd.DataFrame([{
        "id": new_id,
        "username": username,
        "password": password,
        "monthly_income": monthly_income
    }])

    df = pd.concat([df, new_user], ignore_index=True)
    df.to_csv(FILE, index=False)

    print("User registered ✔")


# =========================
# LOGIN + SESSION
# =========================
current_user = None

def login(username, password):
    global current_user

    df = pd.read_csv(FILE)

    user = df[
        (df["username"] == username) &
        (df["password"] == password)
    ]

    if not user.empty:
        current_user = user.iloc[0]
        print("Login successful ✔")
        print("Welcome:", current_user["username"])
        print("Monthly income:", current_user["monthly_income"])
    else:
        print("Invalid credentials ❌")


# =========================
# LOGOUT
# =========================
def logout():
    global current_user
    current_user = None
    print("Logged out ✔")


# =========================
# TEST
# =========================
init_file()

register("kardelen", "1234", 20000)
register("mehmet", "9999", 25000)

login("kardelen", "1234")

logout()