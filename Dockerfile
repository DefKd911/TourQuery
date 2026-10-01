FROM python:3.12-slim

RUN pip install --no-cache-dir uv==0.12.3

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Install dependencies first so code changes don't redo this slow step.
COPY pyproject.toml uv.lock README.md .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 7860
CMD ["uvicorn", "tourquery.api:app", "--host", "0.0.0.0", "--port", "7860"]
