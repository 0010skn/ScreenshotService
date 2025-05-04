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

# 配置pip镜像源以提高下载速度和可靠性
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple/ \
    && pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn \
    && pip install --no-cache-dir --upgrade pip setuptools wheel

# 复制依赖文件
COPY requirements.txt .

# 分步安装Python依赖以提高构建稳定性
RUN pip install --no-cache-dir -r requirements.txt || \
    (pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt)

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