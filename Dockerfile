FROM docker-0.unsee.tech/ubuntu:24.04

WORKDIR /app

# 安装基本工具和Python
RUN apt-get update && apt-get install -y \
    procps \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/code

# 复制依赖文件并安装
COPY requirements.txt /app/
RUN python3 -m venv /app/.venv \
    && . /app/.venv/bin/activate \
    && pip3 install --no-cache-dir -r requirements.txt

# 设置环境变量
ENV CLIENT_DESCRIPTION="Docker Container Client" \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# 复制代码文件
COPY code/ /app/code/

# 设置启动命令
CMD ["python3", "/app/code/client.py"]