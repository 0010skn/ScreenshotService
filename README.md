# 服务器截屏监控

这是一个基于 FastAPI 开发的 Windows 服务器截屏监控工具，每分钟自动截取服务器屏幕，并提供 Web 界面和 API 接口供查看。

## 功能特点

- 每分钟自动截取服务器屏幕
- 自动生成缩略图，提高页面加载速度
- 仅保留最新的 10 张截图，自动清理旧截图
- 提供美观的 Web 界面，使用 Tailwind CSS 设计
- 提供 API 接口，方便与其他系统集成
- 支持查看原图、下载图片等功能

## 环境要求

- Python 3.6+
- Windows 操作系统

## 安装与运行

1. 克隆或下载此代码库到您的服务器

2. 使用自动启动脚本（推荐）

```
双击运行 start.bat
```

该脚本会自动检查 Python 环境，安装所需依赖并启动应用。

3. 手动安装与运行

如果您希望手动安装和启动应用，可以按以下步骤操作：

```bash
# 安装依赖
pip install -r requirements.txt

# 启动应用
python -m app.main
```

4. 访问服务

应用启动后，可通过浏览器访问：http://localhost:8000

## API 接口

- 获取所有截屏列表：`GET /api/screenshots`
- 获取特定截屏：`GET /api/screenshot/{timestamp}`

## 自定义配置

您可以在 `app/main.py` 文件中修改以下配置：

- `MAX_SCREENSHOTS`: 最大保留的截图数量（默认为 10）
- 截图频率：在 `take_screenshot` 函数中的 `time.sleep(60)` 可修改截图间隔（单位为秒）

## 注意事项

- 此应用需要在图形界面环境中运行，无法在纯命令行环境（如服务器的 SSH 会话）中使用
- 由于使用了 pyautogui 进行截屏，应用需要适当的屏幕访问权限
- 如果作为长期服务运行，建议使用 supervisor 或系统服务来管理
