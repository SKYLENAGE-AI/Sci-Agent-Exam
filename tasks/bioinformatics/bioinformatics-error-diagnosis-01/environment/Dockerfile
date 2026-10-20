# Task environment. Builds on the shared base image (../../../harness/base/Dockerfile
# -> sciagent-bench:base), which provides Python 3.11, Node 22, the Claude Code CLI,
# and the common agent/judge tooling. harness/build_image.sh builds the base on first
# use; it also rewrites this FROM line when building a task image directly.
FROM sciagent-bench:base

# ripgrep satisfies harbor's required-command check (curl/bash/node/npm/rg).
RUN apt-get update && apt-get install -y --no-install-recommends ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Task scientific stack — exact pins captured from the evaluation image (Python 3.11.15).
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock

# Mounted task data (datasets, source code, papers). The agent sees only this.
COPY data/ /home/agent/data/
RUN mkdir -p /home/agent/results
WORKDIR /home/agent
# Note: the offline NTAB fork under data/broken_project is intentionally NOT
# pre-installed; the task is to diagnose and repair it in place.
