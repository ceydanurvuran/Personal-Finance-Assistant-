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

router = APIRouter()

# CONFIG
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_TYPES = [
    "image/png",
    "image/jpeg",
    "application/pdf"
]

# Talha AI Service Key
AI_SERVICE_KEY = "talha_ai_secret"

# Swagger dokümantasyonunda kilit simgesinin kalması ve otomatik hata fırlatmaması için esnek şema
security_scheme = HTTPBearer(auto_error=False)


# UPLOAD RECEIPT
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

    ext = file.content_type.split("/")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    path = os.path.join(UPLOAD_DIR, filename)

    # Save the file
    with open(path, "wb") as f:
        while chunk := file.file.read(1024 * 1024):
            f.write(chunk)

    # DB record
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO files (user_id, filename, filepath, is_analyzed)
        VALUES (?, ?, ?, 0)
    """, (
        user["user_id"],
        file.filename,
        path
    ))

    conn.commit()
    conn.close()

    return {
        "message": "Receipt uploaded",
        "path": path
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


# MARK AS ANALYZED
@router.patch("/files/{file_id}/analyzed")
def mark_as_analyzed(
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
        cursor.execute("UPDATE files SET is_analyzed = 1 WHERE id=?", (file_id,))
    else:
        cursor.execute("UPDATE files SET is_analyzed = 1 WHERE id=? AND user_id=?", 
                       (file_id, token_payload["user_id"]))

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="File not found")

    conn.commit()
    conn.close()

    return {"message": "File marked as analyzed."}