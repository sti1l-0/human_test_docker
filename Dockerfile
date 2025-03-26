FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.9-slim

WORKDIR /app

# 安装基本工具
RUN apt-get update && apt-get install -y \
    procps \
    && rm -rf /var/lib/apt/lists/*

# 创建代码目录
RUN mkdir -p /app/code

# 复制依赖文件
COPY requirements.txt /app/

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 设置环境变量
ENV CLIENT_DESCRIPTION="Docker Container Client"

# 创建挂载点
VOLUME ["/app/code"]

# 运行客户端
CMD ["python", "/app/code/client.py"] 