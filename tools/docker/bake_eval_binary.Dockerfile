FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
        build-essential \
        ca-certificates \
        curl \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN curl -LsSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /workspace
COPY Cargo.lock Cargo.toml ./
COPY crates ./crates
COPY extractor ./extractor
COPY resources ./resources

RUN uv pip install --system ./extractor

ENTRYPOINT [
    "uv",
    "run",
    "--project",
    "extractor",
    "bubbola-full-cycle",
    "--cargo-profile",
    "release"
]
