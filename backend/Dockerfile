FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖（asyncpg 需要 libpq）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# 单 worker: APScheduler 调度器在同进程内运行，多 worker 会导致重复轮询
# 性能通过 asyncio 并发保证（单进程处理几千 QPS 没问题）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

