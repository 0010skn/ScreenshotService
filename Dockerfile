FROM python:3.11-slim

# 安装必要的系统依赖
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    xvfb \
    chromium \
    fonts-wqy-microhei \
    fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 设置虚拟显示以支持pyautogui截图
ENV DISPLAY=:99
ENV PYTHONUNBUFFERED=1

# 暴露应用端口
EXPOSE 8000

# 启动脚本
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# 设置入口点
ENTRYPOINT ["/docker-entrypoint.sh"]

# 默认命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 