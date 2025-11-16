FROM python:3.11-slim

WORKDIR /workspace
COPY pyproject.toml README.md ./
COPY eval_binary ./eval_binary
COPY scripts ./scripts

ENTRYPOINT ["python", "scripts/bake_eval_binary.py"]
