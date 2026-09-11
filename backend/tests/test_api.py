from io import BytesIO

from PIL import Image


def test_process_document_returns_controlled_extraction_error(
    client,
    monkeypatch,
):
    from app.services.extraction_service import ExtractionServiceError

    # Create a real valid PNG in memory.
    image = Image.new("RGB", (100, 100), "white")

    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")

    def mock_extract_document(*args, **kwargs):
        raise ExtractionServiceError()

    monkeypatch.setattr(
        "app.api.routes.documents.extract_document",
        mock_extract_document,
    )

    response = client.post(
        "/api/v1/documents/process",
        files={
            "file": (
                "test.png",
                image_bytes.getvalue(),
                "image/png",
            )
        },
        data={
            "document_type": "invoice",
        },
    )

    assert response.status_code == 503

    data = response.json()

    assert data["detail"]["error"]["code"] == (
        "EXTRACTION_SERVICE_ERROR"
    )

    assert data["detail"]["error"]["message"] == (
        "The document could not be extracted. "
        "Please try again later."
    )