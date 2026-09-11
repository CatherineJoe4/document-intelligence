from sqlalchemy.orm import Session

from app.repositories.document_repository import (
    create_document,
    get_documents,
    get_latest_document,
)


def save_document_result(
    db: Session,
    document_name: str,
    document_type: str,
    status: str,
    file_validation: dict,
    extracted_data: dict,
    financial_validations: list,
    metadata: dict,
):
    return create_document(
        db=db,
        document_name=document_name,
        document_type=document_type,
        status=status,
        file_validation=file_validation,
        extracted_data=extracted_data,
        financial_validations=financial_validations,
        metadata=metadata,
    )


def get_document_by_name(
    db: Session,
    document_name: str,
):
    return get_latest_document(
        db=db,
        document_name=document_name,
    )


def get_all_documents(
    db: Session,
):
    return get_documents(
        db=db,
    )