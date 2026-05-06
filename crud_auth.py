import pandas as pd
import os


TRANSACTION_FILE = "transactions.csv"
USER_FILE = "users.csv"

current_user = None



def init_files():
    if not os.path.exists(USER_FILE):
        pd.DataFrame(columns=["id", "username", "password"]).to_csv(USER_FILE, index=False)

    if not os.path.exists(TRANSACTION_FILE):
        pd.DataFrame(columns=[
            "id", "user_id", "type", "description", "amount", "category"
        ]).to_csv(TRANSACTION_FILE, index=False)



def register(username, password):
    df = pd.read_csv(USER_FILE)

    if username in df["username"].values:
        return False, "User already exists"

    new_id = 1 if df.empty else df["id"].max() + 1

    new_user = pd.DataFrame([{
        "id": new_id,
        "username": username,
        "password": password
    }])

    df = pd.concat([df, new_user], ignore_index=True)
    df.to_csv(USER_FILE, index=False)

    return True, "Account created"



def login(username, password):
    global current_user

    df = pd.read_csv(USER_FILE)

    user = df[(df["username"] == username) & (df["password"] == password)]

    if user.empty:
        return False, "Invalid credentials"

    current_user = user.iloc[0].to_dict()
    return True, "Login successful"



def logout():
    global current_user
    current_user = None



def add_transaction(t_type, description, amount, category):
    if current_user is None:
        return False, "Login required"

    df = pd.read_csv(TRANSACTION_FILE)

    new_id = 1 if df.empty else df["id"].max() + 1

    new_row = pd.DataFrame([{
        "id": new_id,
        "user_id": current_user["id"],
        "type": t_type,
        "description": description,
        "amount": float(amount),
        "category": category
    }])

    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(TRANSACTION_FILE, index=False)

    return True, "Transaction created"



def read_transactions():
    if current_user is None:
        return pd.DataFrame(columns=["id", "user_id", "type", "description", "amount", "category"])

    df = pd.read_csv(TRANSACTION_FILE)
    return df[df["user_id"] == current_user["id"]]



def update_transaction(transaction_id, new_data):
    if current_user is None:
        return False, "Login required"

    df = pd.read_csv(TRANSACTION_FILE)

    mask = (df["id"] == transaction_id) & (df["user_id"] == current_user["id"])

    if not mask.any():
        return False, "Transaction not found"

    if "type" in new_data:
        df.loc[mask, "type"] = new_data["type"]

    if "description" in new_data:
        df.loc[mask, "description"] = new_data["description"]

    if "amount" in new_data:
        df.loc[mask, "amount"] = float(new_data["amount"])

    if "category" in new_data:
        df.loc[mask, "category"] = new_data["category"]

    df.to_csv(TRANSACTION_FILE, index=False)

    return True, "Transaction updated"



def delete_transaction(transaction_id):
    if current_user is None:
        return False, "Login required"

    df = pd.read_csv(TRANSACTION_FILE)

    new_df = df[~((df["id"] == transaction_id) & (df["user_id"] == current_user["id"]))]

    if len(new_df) == len(df):
        return False, "Transaction not found"

    new_df.to_csv(TRANSACTION_FILE, index=False)

    return True, "Transaction deleted"



def calculate_summary():
    data = read_transactions()

    if data.empty:
        return 0, 0, 0

    income = data[data["type"] == "income"]["amount"].sum()
    expense = data[data["type"] == "expense"]["amount"].sum()
    balance = income - expense

    return income, expense, balance


 