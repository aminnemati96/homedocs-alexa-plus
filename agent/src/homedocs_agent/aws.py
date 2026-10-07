"""AWS clients: Bedrock Runtime for the model, Polly for the spoken reply.

Created on first use, so importing the app (for example in tests) needs no
AWS credentials.
"""

from __future__ import annotations

from functools import cache

import boto3
from botocore.config import Config

from homedocs_agent import config

_retry = Config(retries={"total_max_attempts": 4, "mode": "adaptive"})


@cache
def bedrock():
    return boto3.client("bedrock-runtime", region_name=config.AWS_REGION, config=_retry)


@cache
def polly():
    return boto3.client("polly", region_name=config.AWS_REGION, config=_retry)


def synthesize(text: str) -> bytes:
    response = polly().synthesize_speech(
        Text=text,
        OutputFormat="mp3",
        VoiceId=config.POLLY_VOICE,
        Engine="neural",
    )
    return response["AudioStream"].read()
