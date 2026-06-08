import os
import uuid

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Depends,
    HTTPException,
    Header
)
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer
from core import get_connection, verify_token

# 👇 YAPAY ZEKA FİŞ OKUMA MOTORUNU BURAYA DAHİL ETTİK 👇
from receipt_reading import process_receipt 

router = APIRouter()

# CONFIG
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_TYPES = [
    "image/png",
    "image/jpeg",
    "application/pdf"
]

AI_SERVICE_KEY = "talha_ai_secret"
security_scheme = HTTPBearer(auto_error=False)


# UPLOAD & ANALYZE RECEIPT
@router.post("/upload-receipt")
def upload_receipt(
    file: UploadFile = File(...),
    user=Depends(verify_token)
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only PNG, JPG, or PDF files can be uploaded"
        )

    ext_map = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "application/pdf": "pdf"
    }
    ext = ext_map.get(file.content_type, "bin")
    filename = f"{uuid.uuid4()}.{ext}"
    path = os.path.join(UPLOAD_DIR, filename)

    # 1. Dosyayı fiziksel olarak kaydet
    with open(path, "wb") as f:
        while chunk := file.file.read(1024 * 1024):
            f.write(chunk)

    # 2. PADDLE OCR ile fişi oku
    store_name, amount, category = process_receipt(path)

    conn = get_connection()
    cursor = conn.cursor()
    is_analyzed = 1 if amount > 0 else 0

    # 3. Dosya kaydını veritabanına ekle
    cursor.execute("""
        INSERT INTO files (user_id, filename, filepath, is_analyzed)
        VALUES (?, ?, ?, ?)
    """, (user["user_id"], file.filename, path, is_analyzed))

    # 4. Sadece gerçekten tutar okunursa bütçeye gider olarak ekle.
    if amount > 0:
        cursor.execute("""
            INSERT INTO transactions (user_id, type, description, amount, category)
            VALUES (?, 'expense', ?, ?, ?)
        """, (user["user_id"], store_name, amount, category))

    conn.commit()
    conn.close()

    # 5. Sonuçları döndür (live_camera.py bu sonuçları bekliyor)
    return {
        "message": "Receipt uploaded and analyzed" if amount > 0 else "Receipt uploaded but could not be read",
        "path": path,
        "ai_results": {
            "store": store_name,
            "total": amount,
            "category": category,
            "is_analyzed": is_analyzed
        }
    }


# LIST FILES
@router.get("/files")
def get_files(user=Depends(verify_token)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, filename, filepath, is_analyzed, uploaded_at
        FROM files
        WHERE user_id=?
        ORDER BY uploaded_at DESC
    """, (user["user_id"],))

    data = cursor.fetchall()
    conn.close()
    return [dict(i) for i in data]


# DOWNLOAD FILE
@router.get("/files/{file_id}")
def get_file(
    file_id: int,
    x_api_key: str = Header(default=None),
    authorization=Depends(security_scheme)
):
    is_ai = (x_api_key == AI_SERVICE_KEY)
    token_payload = None

    if not is_ai:
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing token or API key")
        try:
            from core import verify_token
            token_payload = verify_token(authorization)
        except Exception as e:
            raise HTTPException(status_code=401, detail=str(e))

    conn = get_connection()
    cursor = conn.cursor()

    if is_ai:
        cursor.execute("SELECT filepath FROM files WHERE id=?", (file_id,))
    else:
        cursor.execute("SELECT filepath FROM files WHERE id=? AND user_id=?", 
                       (file_id, token_payload["user_id"]))

    file = cursor.fetchone()
    conn.close()

    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file["filepath"])
