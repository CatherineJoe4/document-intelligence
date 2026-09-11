from pathlib import Path

import pymupdf
from PIL import Image

from app.services.document_validation_service import validate_document


def create_pdf(path: Path, page_count: int = 1):
    document = pymupdf.open()

    for _ in range(page_count):
        document.new_page()

    document.save(path)
    document.close()


def create_image(path: Path):
    image = Image.new("RGB", (500, 500), "white")
    image.save(path)


def test_valid_pdf(tmp_path):
    file_path = tmp_path / "sample.pdf"

    create_pdf(file_path, page_count=2)

    result = validate_document(
        file_path=str(file_path),
        original_filename="sample.pdf",
        content_type="application/pdf",
    )

    assert result.valid is True
    assert result.code == "VALID"
    assert result.page_count == 2


def test_three_page_pdf_is_valid(tmp_path):
    file_path = tmp_path / "three_pages.pdf"

    create_pdf(file_path, page_count=3)

    result = validate_document(
        file_path=str(file_path),
        original_filename="three_pages.pdf",
        content_type="application/pdf",
    )

    assert result.valid is True
    assert result.page_count == 3


def test_four_page_pdf_is_rejected(tmp_path):
    file_path = tmp_path / "four_pages.pdf"

    create_pdf(file_path, page_count=4)

    result = validate_document(
        file_path=str(file_path),
        original_filename="four_pages.pdf",
        content_type="application/pdf",
    )

    assert result.valid is False
    assert result.code == "PAGE_LIMIT_EXCEEDED"


def test_valid_png(tmp_path):
    file_path = tmp_path / "sample.png"

    create_image(file_path)

    result = validate_document(
        file_path=str(file_path),
        original_filename="sample.png",
        content_type="image/png",
    )

    assert result.valid is True
    assert result.code == "VALID"


def test_unsupported_file_type(tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("hello")

    result = validate_document(
        file_path=str(file_path),
        original_filename="sample.txt",
        content_type="text/plain",
    )

    assert result.valid is False
    assert result.code == "UNSUPPORTED_FILE_TYPE"


def test_empty_file(tmp_path):
    file_path = tmp_path / "empty.pdf"
    file_path.write_bytes(b"")

    result = validate_document(
        file_path=str(file_path),
        original_filename="empty.pdf",
        content_type="application/pdf",
    )

    assert result.valid is False
    assert result.code == "EMPTY_FILE"