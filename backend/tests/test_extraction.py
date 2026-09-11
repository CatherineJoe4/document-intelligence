from pathlib import Path

import pytest

from app.services.extraction_service import (
    ExtractionServiceError,
    extract_document,
)


def test_extraction_service_error_is_raised_for_gemini_failure(
    monkeypatch,
    tmp_path,
):
    test_file = tmp_path / "test.png"
    test_file.write_bytes(b"fake image content")

    class FakeModels:
        def generate_content(self, **kwargs):
            raise RuntimeError("Simulated Gemini failure")

    class FakeClient:
        models = FakeModels()

    monkeypatch.setattr(
        "app.services.extraction_service.genai.Client",
        lambda api_key: FakeClient(),
    )

    with pytest.raises(ExtractionServiceError) as exc_info:
        extract_document(
            file_path=str(test_file),
            document_type="invoice",
        )

    assert exc_info.value.code == "EXTRACTION_SERVICE_ERROR"
    assert (
        exc_info.value.message
        == "The document could not be extracted. Please try again later."
    )