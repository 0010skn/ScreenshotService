import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import shutil
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
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
MAX_SCREENSHOTS = 100000
PAGE_SIZE = 12  # 每页显示的截图数量
SCREENSHOT_INTERVAL = 60  # 截图间隔（秒）

# 截图锁，防止并发截图
screenshot_lock = threading.Lock()

def generate_thumbnail(screenshot_path, thumbnail_path):
    """生成缩略图"""
    with Image.open(screenshot_path) as img:
        img.thumbnail((300, 200))
        img.save(thumbnail_path)

def take_single_screenshot():
    """执行单次截图，由定时器调用"""
    global screenshots
    
    # 获取锁，防止并发执行
    if not screenshot_lock.acquire(blocking=False):
        print("另一个截图任务正在执行，跳过本次截图")
        return
    
    try:
        # 获取当前时间
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        
        # 截屏并保存
        screenshot_path = SCREENSHOTS_DIR / f"screenshot_{timestamp}.png"
        thumbnail_path = THUMBNAILS_DIR / f"thumbnail_{timestamp}.png"
        
        screenshot_success = False
        
        try:
            # 使用pyautogui进行截屏
            screenshot = pyautogui.screenshot()
            screenshot.save(screenshot_path)
            screenshot_success = True
            
            # 生成缩略图
            try:
                generate_thumbnail(screenshot_path, thumbnail_path)
            except Exception as thumb_err:
                print(f"生成缩略图失败: {thumb_err}")
                # 如果缩略图生成失败，尝试复制原图作为缩略图
                if os.path.exists(screenshot_path):
                    try:
                        shutil.copy(screenshot_path, thumbnail_path)
                    except Exception:
                        pass
            
            # 更新截屏列表
            screenshots.append({
                "filename": f"screenshot_{timestamp}.png",
                "thumbnail": f"screenshots/thumbnails/thumbnail_{timestamp}.png",
                "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp": timestamp
            })
            
            # 按时间倒序排序（确保最新的在前面）
            screenshots.sort(key=lambda x: x["timestamp"], reverse=True)
            
            # 如果超过最大数量，删除最早的截屏
            if len(screenshots) > MAX_SCREENSHOTS:
                # 因为已经按时间倒序排序，最早的截屏是列表的最后一项
                oldest = screenshots.pop(-1)
                oldest_file = SCREENSHOTS_DIR / oldest["filename"]
                oldest_thumbnail = THUMBNAILS_DIR / f"thumbnail_{oldest['timestamp']}.png"
                
                # 删除文件（如果存在）
                if os.path.exists(oldest_file):
                    os.remove(oldest_file)
                if os.path.exists(oldest_thumbnail):
                    os.remove(oldest_thumbnail)
                
                print(f"删除旧截图: {oldest['filename']}")
            
            print(f"截图完成: {timestamp}，缩略图路径: screenshots/thumbnails/thumbnail_{timestamp}.png")
            
        except Exception as e:
            print(f"截图过程出错: {e}")
            
            # 清理可能部分创建的文件
            if not screenshot_success:
                if os.path.exists(screenshot_path):
                    try:
                        os.remove(screenshot_path)
                    except Exception:
                        pass
                if os.path.exists(thumbnail_path):
                    try:
                        os.remove(thumbnail_path)
                    except Exception:
                        pass
    
    finally:
        # 释放锁
        screenshot_lock.release()
        
        # 无论成功与否，都安排下一次截图
        schedule_next_screenshot()

def schedule_next_screenshot():
    """安排下一次截图任务"""
    timer = threading.Timer(SCREENSHOT_INTERVAL, take_single_screenshot)
    timer.daemon = True
    timer.start()

def start_screenshot_service():
    """启动截图服务"""
    # 立即执行第一次截图
    threading.Thread(target=take_single_screenshot, daemon=True).start()

# 在应用启动时启动截图服务
@app.on_event("startup")
async def startup_event():
    start_screenshot_service()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主页，显示截屏预览"""
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "current_year": datetime.now().year}
    )

@app.get("/api/screenshots")
async def get_screenshots(
    page: int = Query(1, ge=1),  # 页码，最小为1
    page_size: int = Query(PAGE_SIZE, ge=1, le=100),  # 每页数量，1-100之间
    start_time: Optional[str] = None,  # 开始时间 (格式: YYYYMMDD_HHMMSS)
    end_time: Optional[str] = None,  # 结束时间 (格式: YYYYMMDD_HHMMSS)
    exact_time: Optional[str] = None  # 精确时间 (格式: YYYYMMDD_HHMMSS)
):
    """API 获取截屏信息，支持分页和时间筛选"""
    filtered_screenshots = screenshots.copy()
    
    # 时间筛选
    if exact_time:
        filtered_screenshots = [s for s in filtered_screenshots if s["timestamp"] == exact_time]
    else:
        if start_time:
            filtered_screenshots = [s for s in filtered_screenshots if s["timestamp"] >= start_time]
        if end_time:
            filtered_screenshots = [s for s in filtered_screenshots if s["timestamp"] <= end_time]
    
    # 计算总页数和总数量
    total_count = len(filtered_screenshots)
    total_pages = (total_count + page_size - 1) // page_size
    
    # 分页处理
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_count)
    
    # 返回分页后的数据及分页信息
    return {
        "items": filtered_screenshots[start_idx:end_idx],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "total_count": total_count
        },
        "filters": {
            "start_time": start_time,
            "end_time": end_time,
            "exact_time": exact_time
        }
    }

@app.get("/api/screenshot/{timestamp}")
async def get_screenshot(timestamp: str):
    """获取特定截屏图片"""
    for screenshot in screenshots:
        if screenshot["timestamp"] == timestamp:
            return FileResponse(SCREENSHOTS_DIR / screenshot["filename"])
    return JSONResponse(status_code=404, content={"error": "截屏不存在"})

@app.get("/api/latest")
async def get_latest_screenshot():
    """获取最新的一张截屏"""
    if not screenshots:
        return JSONResponse(status_code=404, content={"error": "暂无截屏"})
    
    # 由于screenshots已经按时间戳倒序排序，第一个就是最新的
    latest = screenshots[0]
    return {
        "screenshot": latest,
        "direct_url": f"/api/screenshot/{latest['timestamp']}"
    }

@app.get("/api/dates", response_model=List[str])
async def get_dates():
    """获取所有有截图的日期列表"""
    dates = set()
    for screenshot in screenshots:
        dates.add(screenshot["timestamp"][:8])  # 提取YYYYMMDD部分
    return sorted(list(dates), reverse=True)  # 按日期倒序返回

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 