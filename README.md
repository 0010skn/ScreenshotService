# 服务器截屏监控

这是一个基于 FastAPI 开发的 Windows 服务器截屏监控工具，每分钟自动截取服务器屏幕，并提供 Web 界面和 API 接口供查看。

Demo 地址：https://160.744000.xyz/

## 服务器截屏与内容抓取工具

这是一个基于 FastAPI 构建的服务器截屏监控工具，它可以：

1. 每分钟自动截取服务器屏幕
2. 保存截图和对应的缩略图
3. 抓取指定网站(如 linux.do)的内容并保存为 HTML 文件
4. 提供 Web 界面和 API 接口查看截图和 HTML 内容

### 功能特点

- **自动截屏**：定时捕获屏幕截图并生成缩略图
- **内容抓取**：从目标网站抓取内容并保存为 HTML 文件
- **网站监控**：同时监控屏幕状态和网站内容变化
- **API 接口**：提供丰富的 API 接口访问历史数据
- **高级抓取**：支持使用各种技术绕过常见的访问限制

### 抓取策略

系统采用多层次的抓取策略，按以下顺序尝试：

1. **RSS Feed 抓取**：尝试获取网站的 RSS feed，通常受限制较少
2. **API 端点抓取**：尝试使用网站的 JSON API 获取内容
3. **HTML 页面抓取**：直接从网站 HTML 中提取内容
4. **备选方案**：如果上述方法都失败，提供友好的错误页面

### 安装和使用

1. 克隆仓库
2. 安装依赖: `pip install -r requirements.txt`
3. 运行应用: `python -m app.main`
4. 访问 http://localhost:8000 查看界面

### 使用 Docker 运行

本项目提供了 Docker 支持，可以方便地使用 Docker 部署和运行。

#### 使用 Docker Compose

1. 确保已安装 Docker 和 Docker Compose
2. 运行以下命令启动服务:

```bash
docker-compose up -d
```

3. 访问 http://localhost:8000 查看界面

#### 使用 Docker 镜像

1. 构建 Docker 镜像:

```bash
docker build -t screenshot-service .
```

2. 运行 Docker 容器:

```bash
docker run -d -p 8000:8000 --name screenshot-service screenshot-service
```

#### 使用预构建的 Docker 镜像

本项目通过 GitHub Actions 自动构建并发布 Docker 镜像，您可以直接使用:

```bash
docker pull ghcr.io/yourusername/screenshot-service:latest
docker run -d -p 8000:8000 --name screenshot-service ghcr.io/yourusername/screenshot-service:latest
```

### API 接口

- `/api/screenshots` - 获取所有截图列表
- `/api/screenshot/{timestamp}` - 获取特定截图
- `/api/html_files` - 获取所有 HTML 文件列表
- `/api/html/{timestamp}` - 获取特定 HTML 文件
- `/api/latest` - 获取最新截图
- `/api/latest_html` - 获取最新 HTML 内容

### 环境要求

- Python 3.8+
- FastAPI
- 其他依赖见 requirements.txt

### 开发者说明

该工具设计用于监控和记录服务器状态，理想用例包括：

- 远程服务器监控
- 网站内容变更追踪
- 界面状态监控

如有问题或建议，请提交 Issue。

## 自定义配置

您可以在 `app/main.py` 文件中修改以下配置：

- `MAX_SCREENSHOTS`: 最大保留的截图数量（默认为 10000）
- 截图频率：在 `take_screenshot` 函数中的 `time.sleep(60)` 可修改截图间隔（单位为秒）

## 注意事项

- 此应用需要在图形界面环境中运行，无法在纯命令行环境（如服务器的 SSH 会话）中使用
- 由于使用了 pyautogui 进行截屏，应用需要适当的屏幕访问权限
- 如果作为长期服务运行，建议使用 supervisor 或系统服务来管理
- 在 Docker 环境中，应用使用 Xvfb 虚拟显示服务器来支持截图功能
