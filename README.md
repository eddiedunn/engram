# Engram

Knowledge corpus service with vector search - your AI's long-term memory.

## Overview

Engram is a FastAPI-based service providing semantic search over a knowledge corpus using PostgreSQL with pgvector. It runs on GPU-enabled infrastructure for fast embedding generation with sentence-transformers.

## Requirements

- **Python**: 3.11+ (3.12+ recommended for production)
- **GPU**: NVIDIA GPU with CUDA support
- **Base Image**: NVIDIA PyTorch 25.12 (for GPU deployment)
- **Database**: PostgreSQL 16 with pgvector extension

## Deployment Architecture

```
Internet/Tailscale → Caddy (TLS termination) → Engram (port 8800) → PostgreSQL + pgvector
```

### Components

- **Caddy**: Reverse proxy with automatic TLS via Step CA ACME
  - Terminates TLS at `engram.your-domain.example.com`
  - Proxies to Engram on `localhost:8800`

- **Engram App**: FastAPI service
  - GPU-accelerated embedding generation
  - Runs in NVIDIA PyTorch container
  - Uses BAAI/bge-large-en-v1.5 model (1024-dim embeddings)

- **PostgreSQL**: Vector database backend
  - pgvector extension for similarity search
  - Separate container on internal network

### Certificate Management

TLS certificates are automatically managed via:
- **Step CA**: Internal ACME server at `your-ca.example.com`
- **Auto-renewal**: Caddy handles certificate lifecycle
- **Zero-trust**: Mesh-only access via Tailscale

## Quick Start

See [deploy/README.md](deploy/README.md) for deployment instructions.

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run locally
python -m engram.cli
```

## License

MIT
