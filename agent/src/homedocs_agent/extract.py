"""Turn an uploaded PDF or photo into a structured document with Bedrock.

The model is forced to call a `record_document` tool, so the reply is always
JSON matching the schema below (the same fields the MCP `save_document` tool takes).
"""

from __future__ import annotations

from datetime import date
from typing import Any

# Converse limits: documents up to 4.5 MB, images up to 3.75 MB.
DOCUMENT_FORMATS = {"application/pdf": "pdf"}
IMAGE_FORMATS = {"image/png": "png", "image/jpeg": "jpeg", "image/webp": "webp"}
MAX_DOCUMENT_BYTES = 4_500_000
MAX_IMAGE_BYTES = 3_750_000

CATEGORIES = ["insurance", "warranty", "housing", "bill", "identity", "vehicle", "medical", "other"]

RECORD_TOOL = {
    "toolSpec": {
        "name": "record_document",
        "description": "Record the key facts of a household document.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short human title, e.g. 'Home insurance policy' or 'Hydro bill, October 2026'.",
                    },
                    "category": {"type": "string", "enum": CATEGORIES},
                    "provider": {"type": "string", "description": "Company or agency that issued it."},
                    "key_dates": {
                        "type": "array",
                        "description": "Renewals, expiries, due dates and notice deadlines.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string", "description": "e.g. 'Payment due', 'Policy renewal'"},
                                "date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                            },
                            "required": ["label", "date"],
                        },
                    },
                    "text": {
                        "type": "string",
                        "description": (
                            "Plain-language summary of everything a person might ask about: amounts, "
                            "coverage, terms, conditions, contact numbers. Several full sentences. "
                            "Only facts stated in the document."
                        ),
                    },
                },
                "required": ["title", "category", "provider", "key_dates", "text"],
            }
        },
    }
}

PROMPT = """Read this household document and record its key facts with the record_document tool.
Today is {today}. Use only what the document says; if a year is missing from a date, \
infer it from the document's context. Leave out account passwords and full card numbers."""


class UnsupportedFile(ValueError):
    pass


def content_block(content_type: str, data: bytes) -> dict[str, Any]:
    if content_type in DOCUMENT_FORMATS:
        if len(data) > MAX_DOCUMENT_BYTES:
            raise UnsupportedFile("PDFs must be 4.5 MB or smaller.")
        # A neutral name: Bedrock warns the name field can carry prompt injection.
        return {"document": {"format": DOCUMENT_FORMATS[content_type], "name": "uploaded document", "source": {"bytes": data}}}
    if content_type in IMAGE_FORMATS:
        if len(data) > MAX_IMAGE_BYTES:
            raise UnsupportedFile("Images must be 3.75 MB or smaller.")
        return {"image": {"format": IMAGE_FORMATS[content_type], "source": {"bytes": data}}}
    raise UnsupportedFile("Upload a PDF, PNG, JPEG or WebP file.")


def extract(converse, model_id: str, content_type: str, data: bytes, today: date | None = None) -> dict[str, Any]:
    """Returns the record_document input: title, category, provider, key_dates, text."""
    block = content_block(content_type, data)
    response = converse(
        modelId=model_id,
        messages=[
            {
                "role": "user",
                "content": [block, {"text": PROMPT.format(today=(today or date.today()).isoformat())}],
            }
        ],
        toolConfig={"tools": [RECORD_TOOL], "toolChoice": {"tool": {"name": "record_document"}}},
        inferenceConfig={"maxTokens": 1500, "temperature": 0},
    )
    for part in response["output"]["message"]["content"]:
        if "toolUse" in part:
            return part["toolUse"]["input"]
    raise RuntimeError("The model did not return the document fields.")
