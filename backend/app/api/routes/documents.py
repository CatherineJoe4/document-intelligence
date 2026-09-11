import logging
import os
import tempfile
from pathlib import Path
from app.services.extraction_service import (
    ExtractionServiceError,
    extract_document,
)
from app.services.financial_validation_service import (
    validate_financial_document,
)
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.document import DocumentType
from app.services.document_service import (
    get_all_documents,
    get_document_by_name,
    save_document_result,
)
from app.services.document_validation_service import validate_document


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)

logger = logging.getLogger(__name__)
settings = get_settings()


@router.post("/process")
async def process_document(
    file: UploadFile = File(...),
    document_type: DocumentType = Form(...),
    db: Session = Depends(get_db),
):
    """
    Upload and validate a supported document.

    Extraction and financial validation will be added
    in the next stages.
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_FILENAME",
                    "message": "The uploaded file has no filename.",
                }
            },
        )

    # ---------------------------------------------------------
    # Save upload temporarily
    # ---------------------------------------------------------
    suffix = Path(file.filename).suffix.lower()

    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
    )

    temp_path = temp_file.name

    try:
        content = await file.read()

        temp_file.write(content)
        temp_file.close()

        # -----------------------------------------------------
        # Validate file BEFORE extraction
        # -----------------------------------------------------
        validation = validate_document(
            file_path=temp_path,
            original_filename=file.filename,
            content_type=file.content_type,
            max_file_size_mb=settings.max_file_size_mb,
            max_pages=settings.max_pages,
        )

        file_validation = {
            "valid": validation.valid,
            "code": validation.code,
            "message": validation.message,
            "file_type": validation.file_type,
            "page_count": validation.page_count,
            "file_size_bytes": validation.file_size_bytes,
        }

        # -----------------------------------------------------
        # Invalid document
        # -----------------------------------------------------
        if not validation.valid:

            logger.warning(
                "Document validation failed: %s | %s",
                file.filename,
                validation.code,
            )

            saved_document = save_document_result(
                db=db,
                document_name=file.filename,
                document_type=document_type.value,
                status="FAILED",
                file_validation=file_validation,
                extracted_data={},
                financial_validations=[],
                metadata={
                    "processing_stage": "file_validation",
                },
            )

            return {
                "document_name": saved_document.document_name,
                "document_type": saved_document.document_type,
                "status": saved_document.status,
                "file_validation": saved_document.file_validation,
                "extracted_data": saved_document.extracted_data,
                "financial_validations": (
                    saved_document.financial_validations
                ),
                "metadata": saved_document.document_metadata,
                "created_at": saved_document.created_at,
                "updated_at": saved_document.updated_at,
            }

        # -----------------------------------------------------
        # Valid document
        # -----------------------------------------------------
        logger.info(
            "Document passed file validation: %s",
            file.filename,
        )

        # Temporary placeholder until extraction service is added.
        # ---------------------------------------------------------
        # Extract document information using Gemini
        # ---------------------------------------------------------
        extracted_data = extract_document(
            file_path=temp_path,
            document_type=document_type.value,
        )

        # ---------------------------------------------------------
        # Financial validation using deterministic Python rules
        # ---------------------------------------------------------
        financial_validations = validate_financial_document(
            document_type=document_type.value,
            extracted_data=extracted_data,
        )

        # ---------------------------------------------------------
        # Determine overall processing status
        # ---------------------------------------------------------
        has_validation_failure = any(
            validation["status"] == "FAIL"
            for validation in financial_validations
        )

        document_status = (
            "FAILED"
            if has_validation_failure
            else "PASS"
        )

        saved_document = save_document_result(
            db=db,
            document_name=file.filename,
            document_type=document_type.value,
            status=document_status,
            file_validation=file_validation,
            extracted_data=extracted_data,
            financial_validations=financial_validations,
            metadata={
                "processing_stage": "financial_validation",
            },
        )

        return {
            "document_name": saved_document.document_name,
            "document_type": saved_document.document_type,
            "status": saved_document.status,
            "file_validation": saved_document.file_validation,
            "extracted_data": saved_document.extracted_data,
            "financial_validations": (
                saved_document.financial_validations
            ),
            "metadata": saved_document.document_metadata,
            "created_at": saved_document.created_at,
            "updated_at": saved_document.updated_at,
        }

    except HTTPException:
        raise

    except ExtractionServiceError as exc:
        logger.error(
            "Document extraction failed | file=%s | code=%s",
            file.filename,
            exc.code,
        )

        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )

    except Exception:
        logger.exception(
            "Unexpected error while processing document: %s",
            file.filename,
        )

        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "PROCESSING_ERROR",
                    "message": (
                        "The document could not be processed."
                    ),
                }
            },
        )

    finally:
        # -----------------------------------------------------
        # Always remove temporary upload
        # -----------------------------------------------------
        try:
            os.unlink(temp_path)
        except OSError:
            pass
@router.get("")
def list_documents(
    db: Session = Depends(get_db),
):
    documents = get_all_documents(db)

    return [
        {
            "document_name": document.document_name,
            "document_type": document.document_type,
            "status": document.status,
            "created_at": document.created_at,
            "updated_at": document.updated_at,
        }
        for document in documents
    ]


@router.get("/{document_name}")
def get_document(
    document_name: str,
    db: Session = Depends(get_db),
):
    document = get_document_by_name(
        db=db,
        document_name=document_name,
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": (
                        f"No processed document found "
                        f"with name '{document_name}'."
                    ),
                }
            },
        )

    return {
        "document_name": document.document_name,
        "document_type": document.document_type,
        "status": document.status,
        "file_validation": document.file_validation,
        "extracted_data": document.extracted_data,
        "financial_validations": document.financial_validations,
        "metadata": document.document_metadata,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }