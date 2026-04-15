# ── Stage 1: Builder (编译阶段) ──────────────────────
FROM python:3.10-slim AS builder

WORKDIR /app

# 1. 换 Debian 12 系统源到阿里云，并安装编译环境
# 注意这里文件路径改为了 /etc/apt/sources.list.d/debian.sources
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev

# 2. 复制依赖并利用 pip 缓存编译
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com

# ── Stage 2: Runtime (运行阶段) ──────────────────────
FROM python:3.10-slim

WORKDIR /app

# 1. 运行环境换源，只安装运行库 libpq
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

# 2. 从 builder 阶段把安装好的 Python 包拷贝过来
COPY --from=builder /root/.local /root/.local
COPY . .

# 3. 确保环境变量包含用户目录下的 Python 包路径
ENV PATH=/root/.local/bin:$PATH

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]