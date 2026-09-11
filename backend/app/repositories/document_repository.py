from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.document import Document


def create_document(
    db: Session,
    document_name: str,
    document_type: str,
    status: str,
    file_validation: dict,
    extracted_data: dict,
    financial_validations: list,
    metadata: dict,
) -> Document:

    document = Document(
        document_name=document_name,
        document_type=document_type,
        status=status,
        file_validation=file_validation,
        extracted_data=extracted_data,
        financial_validations=financial_validations,
       document_metadata=metadata,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def get_latest_document(
    db: Session,
    document_name: str,
) -> Document | None:

    return (
        db.query(Document)
        .filter(Document.document_name == document_name)
        .order_by(desc(Document.created_at))
        .first()
    )


def get_documents(
    db: Session,
) -> list[Document]:

    return (
        db.query(Document)
        .order_by(desc(Document.created_at))
        .all()
    )