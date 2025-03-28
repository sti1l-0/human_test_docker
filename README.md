# Command Execution System

这是一个基于C/S架构的命令执行系统，包含服务端和客户端两个组件。

## 系统架构

- 服务端：提供命令并接收执行结果
- 客户端：在Docker容器中执行命令并返回结果

## 功能特点

- 服务端随机提供系统命令
- 客户端在Docker容器中执行命令
- 记录命令执行时间和输出结果
- 支持错误处理和日志记录

## 安装和运行

### 服务端

1. 进入服务端目录：
```bash
cd server
```

2. 安装依赖：
```bash
pip install -r ../requirements.txt
```

3. 运行服务端：
```bash
python server.py
```

服务端将在 http://localhost:5000 启动。

### 客户端（Docker）

1. 构建Docker镜像：
```bash
docker build -t command-client .
```

2. 运行Docker容器：
```bash
docker run -d --name command-client command-client
```

## API接口

### 获取命令
- 端点：GET /get_command
- 返回：命令ID和命令内容

### 提交结果
- 端点：POST /submit_result
- 参数：
  - command_id: 命令ID
  - execution_time: 执行时间
  - output: 命令输出

## 注意事项

- 确保服务端在客户端容器可以访问的地址运行
- 如需修改服务端地址，请更新 Dockerfile 中的 SERVER_URL 环境变量

# human_test_docker