FROM python:3.9-slim

WORKDIR /app

# 安装基本工具
RUN apt-get update && apt-get install -y \
    procps \
    && rm -rf /var/lib/apt/lists/*

# 复制客户端代码和依赖文件
COPY client/client.py .
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 设置环境变量
ENV SERVER_URL=http://host.docker.internal:5000
ENV CLIENT_DESCRIPTION="Docker Container Client"

# 运行客户端
CMD ["python", "client.py"] 