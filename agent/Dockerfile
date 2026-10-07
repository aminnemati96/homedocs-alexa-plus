# Agent API image for AWS Lambda (arm64). The Lambda Web Adapter extension runs
# the FastAPI app as a normal web server and streams its responses back
# through the function URL, so tool calls still appear live in the browser.
# Build: docker buildx build --platform linux/arm64 --provenance=false -t <repo>:<tag> --push .
FROM python:3.13-slim

COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0 /lambda-adapter /opt/extensions/lambda-adapter
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    AGENT_HOST=127.0.0.1 \
    AGENT_PORT=8080 \
    AWS_LWA_PORT=8080 \
    AWS_LWA_INVOKE_MODE=response_stream \
    AWS_LWA_READINESS_CHECK_PATH=/api/health

CMD ["homedocs-agent"]
