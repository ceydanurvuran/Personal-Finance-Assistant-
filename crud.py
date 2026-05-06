import pandas as pd
import os

FILE = "transactions.csv"


def init_file():
    if not os.path.exists(FILE):
        df = pd.DataFrame(columns=["id", "description", "amount", "category"])
        df.to_csv(FILE, index=False)



def create_transaction(description, amount, category):
    df = pd.read_csv(FILE)

    new_id = 1 if df.empty else df["id"].max() + 1

    new_data = pd.DataFrame([{
        "id": new_id,
        "description": description,
        "amount": amount,
        "category": category
    }])

    df = pd.concat([df, new_data], ignore_index=True)
    df.to_csv(FILE, index=False)



def read_transactions():
    return pd.read_csv(FILE)



def update_transaction(transaction_id, new_amount):
    df = pd.read_csv(FILE)

    df.loc[df["id"] == transaction_id, "amount"] = new_amount

    df.to_csv(FILE, index=False)



def delete_transaction(transaction_id):
    df = pd.read_csv(FILE)

    df = df[df["id"] != transaction_id]

    df.to_csv(FILE, index=False)

   # TEST
# =========================
init_file()

create_transaction("Market", 500, "food")
create_transaction("Coffee", 50, "drink")

print("ALL DATA:")
print(read_transactions())

update_transaction(1, 1000)
delete_transaction(2)

print("AFTER UPDATE/DELETE:")
print(read_transactions())