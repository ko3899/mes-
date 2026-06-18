FROM python:3.10-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 复制代码
COPY . .

# 创建必要目录
RUN mkdir -p logs backups uploads/documents database

# 暴露端口
EXPOSE 8080

# 启动命令
CMD ["python", "production.py"]
