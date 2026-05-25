from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from fastapi import HTTPException, status


def extract_pdf_text_from_bytes(content: bytes) -> str:
    """Extract layout-preserved text from raw PDF bytes using poppler pdftotext.

    Freedom Bank statements rely on debit/credit/description column positions, so
    layout preservation is required for reliable parsing.
    """
    if not content.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is not a PDF",
        )

    with tempfile.TemporaryDirectory(prefix="budget-pdf-") as tmpdir:
        pdf_path = Path(tmpdir) / "statement.pdf"
        txt_path = Path(tmpdir) / "statement.txt"
        pdf_path.write_bytes(content)
        try:
            subprocess.run(
                ["pdftotext", "-layout", str(pdf_path), str(txt_path)],
                check=True,
                capture_output=True,
                timeout=30,
            )
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="PDF text extraction is not configured on the server",
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="PDF text extraction timed out",
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", "replace").strip()
            detail = "Unable to extract text from PDF"
            if stderr:
                detail = f"{detail}: {stderr}"
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=detail,
            ) from exc

        text = txt_path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="PDF contains no extractable text",
            )
        return text
