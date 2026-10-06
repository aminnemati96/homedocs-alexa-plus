"""AWS clients: Bedrock Runtime for the model, Polly for the spoken reply."""

from __future__ import annotations

import boto3
from botocore.config import Config

from homedocs_agent import config

_retry = Config(retries={"total_max_attempts": 4, "mode": "adaptive"})

bedrock = boto3.client("bedrock-runtime", region_name=config.AWS_REGION, config=_retry)
polly = boto3.client("polly", region_name=config.AWS_REGION, config=_retry)


def synthesize(text: str) -> bytes:
    response = polly.synthesize_speech(
        Text=text,
        OutputFormat="mp3",
        VoiceId=config.POLLY_VOICE,
        Engine="neural",
    )
    return response["AudioStream"].read()
