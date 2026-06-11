import os
import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response
from loguru import logger
from app.core.config import settings
from app.services.analyze_service import process_statement, build_excel

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".csv", ".xlsx", ".xls"}


@router.post("/analyze")
async def analyze_statement(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Upload a PDF, CSV, or Excel file.")

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(413, f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit.")
    if not content:
        raise HTTPException(400, "Uploaded file is empty.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        transactions = await process_statement(tmp_path)
    except Exception as e:
        logger.error(f"Parse error: {e}")
        raise HTTPException(422, f"Could not parse statement: {e}")
    finally:
        os.unlink(tmp_path)

    if not transactions:
        raise HTTPException(422, "No transactions found in the uploaded file.")

    excel_bytes = build_excel(transactions)
    stem = Path(file.filename or "statement").stem
    download_name = f"{stem}_categorized.xlsx"

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )
