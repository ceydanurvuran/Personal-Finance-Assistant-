import os
import uuid
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Header
from fastapi.responses import FileResponse
from core import get_connection, verify_token

# SENİN AI MOTORUN BURADA İÇERİ ALINIYOR
from receiptReading import process_receipt

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_TYPES = ["image/png", "image/jpeg", "application/pdf"]
AI_SERVICE_KEY = "talha_ai_secret"

@router.post("/upload-receipt")
def upload_receipt(file: UploadFile = File(...), user=Depends(verify_token)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only PNG, JPG, or PDF files can be uploaded")

    ext = file.content_type.split("/")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    path = os.path.join(UPLOAD_DIR, filename)

    # 1. Dosyayı Kaydet
    with open(path, "wb") as f:
        while chunk := file.file.read(1024 * 1024):
            f.write(chunk)

    # 2. YAPAY ZEKA DEVREYE GİRİYOR (Senin Kodun)
    is_analyzed = 0
    store, total, category = process_receipt(path)
    
    conn = get_connection()
    cursor = conn.cursor()

    # Eğer AI başarıyla okuduysa, doğrudan "Gider" olarak kaydet
    if store != "Unreadable" and total > 0:
        is_analyzed = 1
        cursor.execute("""
            INSERT INTO transactions (user_id, type, description, amount, category)
            VALUES (?, ?, ?, ?, ?)
        """, (user["user_id"], "expense", f"{store} Fişi", total, category))

    # 3. Dosyanın kendisini veritabanına kaydet (Analiz edildi mi bilgisiyle)
    cursor.execute("""
        INSERT INTO files (user_id, filename, filepath, is_analyzed)
        VALUES (?, ?, ?, ?)
    """, (user["user_id"], file.filename, path, is_analyzed))

    conn.commit()
    conn.close()

    return {
        "message": "Receipt uploaded and processed by AI" if is_analyzed else "Receipt uploaded but OCR failed",
        "path": path,
        "ai_results": {
            "store": store,
            "total": total,
            "category": category
        }
    }

@router.get("/files")
def get_files(user=Depends(verify_token)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, filename, filepath, is_analyzed, uploaded_at
        FROM files WHERE user_id=? ORDER BY uploaded_at DESC
    """, (user["user_id"],))
    data = cursor.fetchall()
    conn.close()
    return [dict(i) for i in data]

@router.get("/files/{file_id}")
def get_file(file_id: int, user=Depends(verify_token), x_api_key: str = Header(default=None)):
    conn = get_connection()
    cursor = conn.cursor()
    if x_api_key == AI_SERVICE_KEY:
        cursor.execute("SELECT filepath FROM files WHERE id=?", (file_id,))
    else:
        cursor.execute("SELECT filepath FROM files WHERE id=? AND user_id=?", (file_id, user["user_id"]))
    
    file = cursor.fetchone()
    conn.close()
    if not file: raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file["filepath"])

@router.patch("/files/{file_id}/analyzed")
def mark_as_analyzed(file_id: int, user=Depends(verify_token), x_api_key: str = Header(default=None)):
    conn = get_connection()
    cursor = conn.cursor()
    if x_api_key == AI_SERVICE_KEY:
        cursor.execute("UPDATE files SET is_analyzed = 1 WHERE id=?", (file_id,))
    else:
        cursor.execute("UPDATE files SET is_analyzed = 1 WHERE id=? AND user_id=?", (file_id, user["user_id"]))
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="File not found")
    conn.commit()
    conn.close()
    return {"message": "File marked as analyzed."}