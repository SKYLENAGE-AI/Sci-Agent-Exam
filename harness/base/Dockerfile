FROM python:3.11-slim

# (Optional) Configure a regional apt/pip mirror here for faster builds.

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        poppler-utils \
        build-essential \
        gcc \
        g++ \
        curl \
        git && \
    rm -rf /var/lib/apt/lists/*

# Node.js 22 (required by Claude Code)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code@2.1.170

# Version-agnostic packages only. The scientific stack (numpy/scipy/pandas/
# matplotlib/statsmodels/scikit-learn) is intentionally NOT installed here:
# tasks require different numpy majors (1.24 / 1.26 / 2.x), so a single base
# version would force upgrades/downgrades in the task layer and corrupt numpy
# ("numpy._globals has no attribute '_signature_descriptor'"). Each task's own
# Dockerfile installs the exact scientific versions it needs. Nothing installed
# here may depend on numpy (matplotlib/statsmodels/sklearn would drag it back in).
RUN pip install --no-cache-dir \
    anthropic \
    requests \
    pypdf \
    pdfplumber

# Belt-and-suspenders: ensure NO scientific stack leaks into the base (a transitive
# dep once dragged in numpy 2.x, which then got half-overwritten when a task pinned
# numpy 1.x on top -> corrupted numpy._globals / dtype-ABI crashes). Removing it here
# guarantees each task's own Dockerfile installs numpy/pandas/scipy cleanly.
RUN pip uninstall -y numpy pandas scipy matplotlib scikit-learn statsmodels patsy contourpy 2>/dev/null || true

WORKDIR /home/agent
