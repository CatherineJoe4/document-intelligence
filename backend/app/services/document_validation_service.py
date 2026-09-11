from dataclasses import dataclass
from pathlib import Path

import pymupdf
from PIL import Image


ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}


@dataclass
class FileValidationResult:
    valid: bool
    code: str
    message: str
    file_type: str | None = None
    page_count: int | None = None
    file_size_bytes: int | None = None


def validate_document(
    file_path: str,
    original_filename: str,
    content_type: str | None,
    max_file_size_mb: int = 10,
    max_pages: int = 3,
) -> FileValidationResult:

    path = Path(file_path)

    # ---------------------------------------------------------
    # 1. File existence
    # ---------------------------------------------------------
    if not path.exists() or not path.is_file():
        return FileValidationResult(
            valid=False,
            code="FILE_NOT_FOUND",
            message="The uploaded file could not be found.",
        )

    # ---------------------------------------------------------
    # 2. Empty file check
    # ---------------------------------------------------------
    file_size = path.stat().st_size

    if file_size == 0:
        return FileValidationResult(
            valid=False,
            code="EMPTY_FILE",
            message="The uploaded file is empty.",
            file_size_bytes=file_size,
        )

    # ---------------------------------------------------------
    # 3. File size check
    # ---------------------------------------------------------
    max_size_bytes = max_file_size_mb * 1024 * 1024

    if file_size > max_size_bytes:
        return FileValidationResult(
            valid=False,
            code="FILE_TOO_LARGE",
            message=(
                f"File exceeds the maximum allowed size "
                f"of {max_file_size_mb} MB."
            ),
            file_size_bytes=file_size,
        )

    # ---------------------------------------------------------
    # 4. Extension check
    # ---------------------------------------------------------
    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        return FileValidationResult(
            valid=False,
            code="UNSUPPORTED_FILE_TYPE",
            message="Only PDF, JPG, and PNG files are supported.",
            file_size_bytes=file_size,
        )

    # ---------------------------------------------------------
    # 5. MIME type check
    # ---------------------------------------------------------
    if content_type and content_type.lower() not in ALLOWED_MIME_TYPES:
        return FileValidationResult(
            valid=False,
            code="UNSUPPORTED_FILE_TYPE",
            message="The uploaded file type is not supported.",
            file_size_bytes=file_size,
        )

    # ---------------------------------------------------------
    # 6. PDF validation
    # ---------------------------------------------------------
    if extension == ".pdf":

        try:
            document = pymupdf.open(file_path)

            page_count = len(document)

            if page_count == 0:
                document.close()

                return FileValidationResult(
                    valid=False,
                    code="INVALID_DOCUMENT",
                    message="The PDF contains no readable pages.",
                    file_type="pdf",
                    page_count=0,
                    file_size_bytes=file_size,
                )

            # IMPORTANT:
            # Page limit is checked before extraction/OCR.
            if page_count > max_pages:
                document.close()

                return FileValidationResult(
                    valid=False,
                    code="PAGE_LIMIT_EXCEEDED",
                    message=(
                        f"PDF contains {page_count} pages. "
                        f"The maximum allowed is {max_pages} pages."
                    ),
                    file_type="pdf",
                    page_count=page_count,
                    file_size_bytes=file_size,
                )

            # Try accessing every page to catch corrupted PDFs.
            for page_number in range(page_count):
                document.load_page(page_number)

            document.close()

            return FileValidationResult(
                valid=True,
                code="VALID",
                message="PDF passed validation.",
                file_type="pdf",
                page_count=page_count,
                file_size_bytes=file_size,
            )

        except Exception:
            return FileValidationResult(
                valid=False,
                code="CORRUPT_FILE",
                message="The PDF could not be opened or read.",
                file_type="pdf",
                file_size_bytes=file_size,
            )

    # ---------------------------------------------------------
    # 7. Image validation
    # ---------------------------------------------------------
    try:
        with Image.open(file_path) as image:
            image.verify()

        # Reopen because verify() invalidates the image object.
        with Image.open(file_path) as image:
            image.load()

        return FileValidationResult(
            valid=True,
            code="VALID",
            message="Image passed validation.",
            file_type=extension.lstrip("."),
            page_count=1,
            file_size_bytes=file_size,
        )

    except Exception:
        return FileValidationResult(
            valid=False,
            code="CORRUPT_FILE",
            message="The image could not be opened or read.",
            file_type=extension.lstrip("."),
            file_size_bytes=file_size,
        )