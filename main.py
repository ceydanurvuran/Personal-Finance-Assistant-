
# AI FINANCIAL ASSISTANT
# FastAPI + SQLite + JWT + FULL CRUD


from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jwt import ExpiredSignatureError, InvalidTokenError

app = FastAPI(title="Finance Backend")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# CONFIG

DB_NAME = "finance.db"
SECRET_KEY = "kardelen_proje_2026"
ALGORITHM = "HS256"

security = HTTPBearer()
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# DATABASE

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        description TEXT,
        amount REAL,
        category TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

init_db()


# MODELS

class User(BaseModel):
    username: str
    password: str


class Transaction(BaseModel):
    type: str
    description: str
    amount: float
    category: str


# JWT

def create_token(user_id, username):
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=2)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    if not token:
        raise HTTPException(status_code=401, detail="Token not provided")

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        return payload

    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")

    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


# AUTH

@app.post("/register")
def register(user: User):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        hashed_pw = pwd_context.hash(user.password)

        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (user.username, hashed_pw)
        )

        conn.commit()
        return {"message": "Registration successful"}

    except sqlite3.IntegrityError:
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

    if not db_user:
        raise HTTPException(status_code=401, detail="User not found")

    if not pwd_context.verify(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Incorrect password")

    token = create_token(db_user["id"], db_user["username"])

    return {"access_token": token, "token_type": "bearer"}


# CREATE

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


# READ

@app.get("/transactions")
def get_transactions(user=Depends(verify_token)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM transactions WHERE user_id=?",
        (user["user_id"],)
    )

    data = cursor.fetchall()
    conn.close()

    return [dict(row) for row in data]

# UPDATE

@app.put("/transactions/{id}")
def update_transaction(id: int, t: Transaction, user=Depends(verify_token)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE transactions 
        SET type=?, description=?, amount=?, category=?
        WHERE id=? AND user_id=?
    """, (t.type, t.description, t.amount, t.category, id, user["user_id"]))

    conn.commit()
    conn.close()

    return {"message": "Transaction updated"}


# DELETE

@app.delete("/transactions/{id}")
def delete_transaction(id: int, user=Depends(verify_token)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM transactions WHERE id=? AND user_id=?",
        (id, user["user_id"])
    )

    conn.commit()
    conn.close()

    return {"message": "Transaction deleted"}


# SUMMARY

@app.get("/summary")
def summary(user=Depends(verify_token)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT type, SUM(amount) as total
        FROM transactions
        WHERE user_id=?
        GROUP BY type
    """, (user["user_id"],))

    data = cursor.fetchall()
    conn.close()

    result = {"income": 0, "expense": 0}

    for r in data:
        result[r["type"]] = r["total"]

    result["balance"] = result["income"] - result["expense"]

    return result