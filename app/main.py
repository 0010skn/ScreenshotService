import os
import time
from datetime import datetime
from pathlib import Path
from typing import List
import shutil
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import pyautogui
import threading
import uvicorn
from PIL import Image

app = FastAPI(title="截屏服务")

# 静态文件和模板配置
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# 添加当前年份的Jinja2过滤器
templates.env.globals["now"] = lambda: datetime.now()

# 截屏保存目录
SCREENSHOTS_DIR = Path("app/static/screenshots")
THUMBNAILS_DIR = Path("app/static/screenshots/thumbnails")
os.makedirs(THUMBNAILS_DIR, exist_ok=True)

# 全局变量，用于存储截屏信息
screenshots = []
MAX_SCREENSHOTS = 10

def generate_thumbnail(screenshot_path, thumbnail_path):
    """生成缩略图"""
    with Image.open(screenshot_path) as img:
        img.thumbnail((300, 200))
        img.save(thumbnail_path)

def take_screenshot():
    """截屏函数"""
    global screenshots
    
    while True:
        try:
            # 获取当前时间
            now = datetime.now()
            timestamp = now.strftime("%Y%m%d_%H%M%S")
            
            # 截屏并保存
            screenshot_path = SCREENSHOTS_DIR / f"screenshot_{timestamp}.png"
            thumbnail_path = THUMBNAILS_DIR / f"thumbnail_{timestamp}.png"
            
            # 使用pyautogui进行截屏
            screenshot = pyautogui.screenshot()
            screenshot.save(screenshot_path)
            
            # 生成缩略图
            generate_thumbnail(screenshot_path, thumbnail_path)
            
            # 更新截屏列表
            screenshots.append({
                "filename": f"screenshot_{timestamp}.png",
                "thumbnail": f"screenshots/thumbnails/thumbnail_{timestamp}.png",
                "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp": timestamp
            })
            
            # 如果超过最大数量，删除最早的截屏
            if len(screenshots) > MAX_SCREENSHOTS:
                oldest = screenshots.pop(0)
                os.remove(SCREENSHOTS_DIR / oldest["filename"])
                os.remove(THUMBNAILS_DIR / f"thumbnail_{oldest['timestamp']}.png")
            
            # 按时间倒序排序
            screenshots.sort(key=lambda x: x["timestamp"], reverse=True)
            
            print(f"截图完成: {timestamp}，缩略图路径: screenshots/thumbnails/thumbnail_{timestamp}.png")
            
            # 每10秒截屏一次
            time.sleep(10)
        except Exception as e:
            print(f"截屏出错: {e}")
            time.sleep(10)  # 出错后稍等一会再重试

# 启动截屏线程
screenshot_thread = threading.Thread(target=take_screenshot, daemon=True)
screenshot_thread.start()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主页，显示截屏预览"""
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "screenshots": screenshots, "current_year": datetime.now().year}
    )

@app.get("/api/screenshots", response_model=List[dict])
async def get_screenshots():
    """API 获取所有截屏信息"""
    return screenshots

@app.get("/api/screenshot/{timestamp}")
async def get_screenshot(timestamp: str):
    """获取特定截屏图片"""
    for screenshot in screenshots:
        if screenshot["timestamp"] == timestamp:
            return FileResponse(SCREENSHOTS_DIR / screenshot["filename"])
    return {"error": "截屏不存在"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 