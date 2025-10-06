FROM python:3.9-slim

# Install system dependencies including C++ compiler
RUN apt-get update \
    && apt-get install -y \
        git \
        libspatialindex-dev \
        libgdal-dev \
        libproj-dev \
        curl \
        build-essential \
        g++ \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Install pdgstaging from GitHub repo using uv
RUN uv pip install --system git+https://github.com/PermafrostDiscoveryGateway/viz-3dtiles.git@feature-3dt-k8s

WORKDIR /app