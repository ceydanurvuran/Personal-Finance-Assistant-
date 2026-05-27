import sqlite3
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core import get_connection, create_token, verify_token, hash_password, verify_password
from ai_context import router as ai_router
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
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        description TEXT,
        amount REAL,
        category TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        filename TEXT,
        filepath TEXT,
        is_analyzed INTEGER DEFAULT 0,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                    (user.username, hash_password(user.password)))
        conn.commit()
        return {"message": "created"}
    except sqlite3.IntegrityError:
        raise HTTPException(400, "exists")
    except Exception as e:
        raise HTTPException(500, f"Internal server error: {str(e)}")
    finally:
        conn.close()


@app.post("/login")
def login(user: User):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE username=?", (user.username,))
    db = cur.fetchone()
    conn.close()

    if not db:
        raise HTTPException(401)

    if not verify_password(user.password, db["password"]):
        raise HTTPException(401)

    return {"access_token": create_token(db["id"], db["username"])}


@app.post("/transactions")
def add(t: Transaction, user=Depends(verify_token)):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO transactions (user_id, type, description, amount, category)
        VALUES (?, ?, ?, ?, ?)
    """, (user["user_id"], t.type, t.description, t.amount, t.category))

    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/transactions")
def list_t(user=Depends(verify_token)):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM transactions WHERE user_id=?", (user["user_id"],))
    data = cur.fetchall()
    conn.close()

    return [dict(i) for i in data]


@app.put("/transactions/{id}")
def update(id: int, t: Transaction, user=Depends(verify_token)):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE transactions
        SET type=?, description=?, amount=?, category=?
        WHERE id=? AND user_id=?
    """, (t.type, t.description, t.amount, t.category, id, user["user_id"]))

    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(404)

    conn.commit()
    conn.close()
    return {"ok": True}


@app.delete("/transactions/{id}")
def delete(id: int, user=Depends(verify_token)):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (id, user["user_id"]))

    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(404)

    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/summary")
def summary(user=Depends(verify_token)):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT type, SUM(amount) as total
        FROM transactions
        WHERE user_id=?
        GROUP BY type
    """, (user["user_id"],))

    rows = cur.fetchall()
    conn.close()

    res = {"income": 0, "expense": 0}
    for r in rows:
        res[r["type"]] = r["total"] or 0

    res["balance"] = res["income"] - res["expense"]
    return res

app.include_router(file_router)
app.include_router(ai_router)