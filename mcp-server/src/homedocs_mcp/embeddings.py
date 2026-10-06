"""Text embeddings with Amazon Titan Text Embeddings V2 on Bedrock."""

from __future__ import annotations

import json

import boto3
from botocore.config import Config

DEFAULT_MODEL_ID = "amazon.titan-embed-text-v2:0"


class TitanEmbedder:
    def __init__(
        self,
        region: str = "us-east-1",
        model_id: str = DEFAULT_MODEL_ID,
        dimensions: int = 1024,
    ):
        self.model_id = model_id
        self.dimensions = dimensions
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(retries={"total_max_attempts": 4, "mode": "adaptive"}),
        )

    def embed(self, text: str) -> list[float]:
        response = self._client.invoke_model(
            modelId=self.model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(
                {"inputText": text, "dimensions": self.dimensions, "normalize": True}
            ),
        )
        return json.loads(response["body"].read())["embedding"]
