from datetime import date

import pytest

from homedocs_agent.extract import UnsupportedFile, content_block, extract

FIELDS = {
    "title": "Hydro bill, October 2026",
    "category": "bill",
    "provider": "Nova Power",
    "key_dates": [{"label": "Payment due", "date": "2026-10-28"}],
    "text": "Amount due is $112.40 by October 28, 2026.",
}


def test_pdf_becomes_a_document_block_with_a_neutral_name():
    block = content_block("application/pdf", b"%PDF-1.7")
    assert block["document"]["format"] == "pdf"
    assert block["document"]["name"] == "uploaded document"


def test_photo_becomes_an_image_block():
    assert content_block("image/jpeg", b"...")["image"]["format"] == "jpeg"


@pytest.mark.parametrize(
    "content_type, size",
    [("text/plain", 10), ("application/pdf", 5_000_000), ("image/png", 4_000_000)],
)
def test_rejects_wrong_type_or_too_big(content_type, size):
    with pytest.raises(UnsupportedFile):
        content_block(content_type, b"x" * size)


def test_extract_forces_the_record_tool_and_returns_its_input():
    seen = {}

    def converse(**kwargs):
        seen.update(kwargs)
        return {"output": {"message": {"content": [{"toolUse": {"toolUseId": "1", "name": "record_document", "input": FIELDS}}]}}}

    assert extract(converse, "model", "application/pdf", b"%PDF", today=date(2026, 10, 7)) == FIELDS
    assert seen["toolConfig"]["toolChoice"] == {"tool": {"name": "record_document"}}
    assert "2026-10-07" in seen["messages"][0]["content"][1]["text"]
