FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /workspace
COPY . .
RUN uv pip install --system ./extractor

ENTRYPOINT ["uv", "run", "--project", "extractor", "python", "scripts/bake_eval_binary.py"]
