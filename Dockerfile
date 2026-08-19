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

# 健康检查（使用 /healthz 接口，无需 curl）
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')"

# 启动命令
CMD ["python", "production.py"]
