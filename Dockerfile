FROM node:22-bookworm-slim AS node-runtime

FROM python:3.12

WORKDIR /tanpopo

RUN apt-get update && \
    apt-get install -y --no-install-recommends git openssh-client ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Provide npx for official Node-based MCP servers without installing Debian node/npm packages.
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -sf ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    ln -sf ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# 安装项目依赖
COPY requirements.txt .
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN pip install --upgrade pip -i "${PIP_INDEX_URL}" && \
    pip install --default-timeout=60 -i "${PIP_INDEX_URL}" -r requirements.txt

ENV PATH="/root/.local/bin:${PATH}"
RUN uv tool install --default-index "${PIP_INDEX_URL}" mcp-server-fetch==2025.4.7 && \
    ln -sf /root/.local/bin/mcp-server-fetch /usr/local/bin/mcp-server-fetch

# 项目初始环境配置
COPY . .
RUN mkdir tmp

CMD sh ./start.sh && python run.py
