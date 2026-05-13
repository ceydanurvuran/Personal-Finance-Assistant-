from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from core import get_connection, create_token, verify_token, hash_password, verify_password
from file_upload import router as file_router

app = FastAPI(title="Finance Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT,
        description TEXT, amount REAL, category TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, filename TEXT,
        filepath TEXT, is_analyzed INTEGER DEFAULT 0, uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()

init_db()

class User(BaseModel):
    username: str
    password: str

class Transaction(BaseModel):
    type: str
    description: str
    amount: float
    category: str

@app.post("/register")
def register(user: User):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        hashed_password = hash_password(user.password)
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (user.username, hashed_password))
        conn.commit()
        return {"message": "User created"}
    except:
        raise HTTPException(status_code=400, detail="User already exists")
    finally:
        conn.close()

@app.post("/login")
def login(user: User):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username=?", (user.username,))
    db_user = cursor.fetchone()
    conn.close()

    if not db_user: raise HTTPException(status_code=401, detail="User not found")
    if not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Incorrect password")

    token = create_token(db_user["id"], db_user["username"])
    return {"access_token": token, "token_type": "bearer"}

@app.post("/transactions")
def add_transaction(t: Transaction, user=Depends(verify_token)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (user_id, type, description, amount, category)
        VALUES (?, ?, ?, ?, ?)
    """, (user["user_id"], t.type, t.description, t.amount, t.category))
    conn.commit()
    conn.close()
    return {"message": "Transaction added"}

@app.get("/transactions")
def get_transactions(user=Depends(verify_token)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY date DESC", (user["user_id"],))
    data = cursor.fetchall()
    conn.close()
    return [dict(i) for i in data]

@app.put("/transactions/{transaction_id}")
def update_transaction(transaction_id: int, t: Transaction, user=Depends(verify_token)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE transactions SET type=?, description=?, amount=?, category=?
        WHERE id=? AND user_id=?
    """, (t.type, t.description, t.amount, t.category, transaction_id, user["user_id"]))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Transaction not found")
    conn.commit()
    conn.close()
    return {"message": "Transaction updated"}

@app.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: int, user=Depends(verify_token)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (transaction_id, user["user_id"]))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Transaction not found")
    conn.commit()
    conn.close()
    return {"message": "Transaction deleted"}

@app.get("/summary")
def summary(user=Depends(verify_token)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT type, SUM(amount) as total FROM transactions WHERE user_id=? GROUP BY type", (user["user_id"],))
    data = cursor.fetchall()
    conn.close()

    result = {"income": 0, "expense": 0}
    for r in data:
        if r["type"] in result:
            result[r["type"]] = r["total"] or 0
    result["balance"] = result["income"] - result["expense"]
    return result

app.include_router(file_router)