import os
import time
import random
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
import requests  # 添加requests库用于抓取网页
import json
import re
import html  # 用于HTML转义，提高安全性

# Selenium相关导入
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

app = FastAPI(title="截屏服务")

# 静态文件和模板配置
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# 添加当前年份的Jinja2过滤器
templates.env.globals["now"] = lambda: datetime.now()

# 截屏保存目录
SCREENSHOTS_DIR = Path("app/static/screenshots")
THUMBNAILS_DIR = Path("app/static/screenshots/thumbnails")
HTML_DIR = Path("app/static/screenshots/html")  # 新增：HTML文件保存目录
os.makedirs(THUMBNAILS_DIR, exist_ok=True)
os.makedirs(HTML_DIR, exist_ok=True)  # 创建HTML文件保存目录

# 全局变量，用于存储截屏信息
screenshots = []
html_files = []  # 新增：存储HTML文件信息
MAX_SCREENSHOTS = 100000
PAGE_SIZE = 12  # 每页显示的截图数量
SCREENSHOT_INTERVAL = 60  # 截图间隔（秒）
WEBSITE_URL = "https://linux.do"  # 需要抓取的网站URL
RAW_URL = "https://linux.do/raw"  # Discourse 原始内容API
MAX_RETRY_COUNT = 3  # 获取HTML的最大重试次数

# 尝试不同的API端点
API_ENDPOINTS = [
    "https://linux.do/latest.json",
    "https://linux.do/posts.json",  # 添加posts接口获取最新帖子
    "https://linux.do/categories.json",
    "https://linux.do/c/1.json",  # 通常第一个分类是"不分类"或"综合讨论"
    "https://linux.do/top.json",
    "https://linux.do/tags.json",
    "https://linux.do/top/weekly.json",  # 添加每周热门主题
    "https://linux.do/top/monthly.json"  # 添加每月热门主题
]

# 截图锁，防止并发截图
screenshot_lock = threading.Lock()

# 用户代理列表，模拟不同浏览器
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
]

# Cookies - 有时需要cookie才能访问Discourse论坛
DEFAULT_COOKIES = {
    "_t": "unused",                     # 一些Discourse论坛要求这个cookie
    "discourse_locale": "zh_CN",
    "_forum_session": "unused",
    "destination_url": "forum.json",
    "seen-log-out-notice": "true",
    "theme_ids": "8",
    "_ga": "GA1.2.123456789.1613745761", 
    "_gid": "GA1.2.123456789.1613745761",
}

# 常见API密钥参数名称，大多数Discourse实例会检查这些参数
API_KEY_PARAMS = {
    "api_key": "699667f923873c5a7c638d2b97b7b7f2",  # 随机值，模拟API密钥
    "api_username": "system",                       # 通常是'system'或'admin'
}

# 代理服务器列表 - 如果需要绕过IP限制
PROXY_LIST = [
    None,  # 首先尝试不使用代理
    # 以下是示例代理，请替换为实际可用的代理
    # "http://user:pass@proxy1.example.com:8080",
    # "http://user:pass@proxy2.example.com:8080",
]

def generate_headers(referrer=None):
    """生成随机的、逼真的HTTP头"""
    user_agent = random.choice(USER_AGENTS)
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Requested-With": "XMLHttpRequest",
        "DNT": "1",  # Do Not Track
        "Cache-Control": "max-age=0",
    }
    
    # 如果提供了引用页，添加Referer头
    if referrer:
        headers["Referer"] = referrer
    
    # 随机添加一些额外的头
    if random.random() > 0.5:
        headers["Pragma"] = "no-cache"
    
    if random.random() > 0.5:
        headers["Sec-CH-UA"] = '"Google Chrome";v="120", "Not)A;Brand";v="8", "Chromium";v="120"'
        
    if random.random() > 0.5:
        headers["Sec-CH-UA-Mobile"] = "?0"
        
    if random.random() > 0.5:
        headers["Sec-CH-UA-Platform"] = '"Windows"'
    
    return headers

def generate_thumbnail(screenshot_path, thumbnail_path):
    """生成缩略图"""
    with Image.open(screenshot_path) as img:
        img.thumbnail((300, 200))
        img.save(thumbnail_path)

def make_api_request(url, method="GET", params=None, json_data=None, use_api_key=False, proxy_index=0):
    """发送API请求，支持多种选项和重试"""
    if proxy_index >= len(PROXY_LIST):
        return None, 0
    
    try:
        # 选择当前代理
        current_proxy = PROXY_LIST[proxy_index]
        
        # 准备请求参数
        request_params = {}
        if params:
            request_params.update(params)
        
        # 如果需要使用API密钥，添加相关参数
        if use_api_key:
            request_params.update(API_KEY_PARAMS)
        
        # 生成随机头
        headers = generate_headers(referrer=WEBSITE_URL)
        
        # 准备请求
        session = requests.Session()
        session.cookies.update(DEFAULT_COOKIES)
        
        # 设置代理
        proxies = {"http": current_proxy, "https": current_proxy} if current_proxy else None
        
        # 发送请求
        if method.upper() == "GET":
            response = session.get(
                url, 
                headers=headers, 
                params=request_params,
                proxies=proxies,
                timeout=30
            )
        elif method.upper() == "POST":
            response = session.post(
                url, 
                headers=headers, 
                params=request_params,
                json=json_data,
                proxies=proxies,
                timeout=30
            )
        
        return response, response.status_code
        
    except Exception as e:
        print(f"请求 {url} 失败: {e}")
        # 尝试下一个代理
        return make_api_request(url, method, params, json_data, use_api_key, proxy_index + 1)

def fetch_latest_posts_from_html():
    """通过主页HTML抓取最新帖子"""
    try:
        # 使用增强的请求方法
        response, status_code = make_api_request(WEBSITE_URL)
        
        if not response or status_code != 200:
            print(f"获取主页失败，状态码: {status_code}")
            return None, False
        
        html_content = response.text
        
        # 查找并提取主题ID和链接
        # Discourse主题链接格式通常为 /t/{slug}/{id}
        topic_pattern = r'/t/([^/]+)/(\d+)'
        matches = re.findall(topic_pattern, html_content)
        
        if matches:
            print(f"从主页找到 {len(matches)} 个主题")
            # 获取第一个匹配的主题
            slug, topic_id = matches[0]
            return fetch_raw_topic(topic_id)
        else:
            print("在主页未找到主题链接")
            
            # 尝试查找JSON数据，Discourse通常会在页面中嵌入preload数据
            json_pattern = r'PreloadStore\.store\("topic_list",\s*(\{.*?\})\);'
            json_matches = re.findall(json_pattern, html_content, re.DOTALL)
            
            if json_matches:
                try:
                    topic_data = json.loads(json_matches[0])
                    if "topics" in topic_data and topic_data["topics"]:
                        topic_id = topic_data["topics"][0].get("id")
                        if topic_id:
                            return fetch_topic_by_id(topic_id)
                except Exception as e:
                    print(f"解析嵌入的JSON数据失败: {e}")
        
        return None, False
    except Exception as e:
        print(f"通过HTML抓取最新帖子失败: {e}")
        return None, False

def fetch_raw_topic(topic_id):
    """使用/raw/接口获取特定主题的原始内容"""
    try:
        url = f"{RAW_URL}/{topic_id}"
        print(f"尝试获取原始主题内容: {url}")
        
        # 使用增强的请求方法
        response, status_code = make_api_request(url, referrer=f"{WEBSITE_URL}/t/{topic_id}")
        
        if not response or status_code != 200:
            print(f"获取原始主题内容失败，状态码: {status_code}")
            # 如果/raw接口失败，尝试正常的主题API
            return fetch_topic_by_id(topic_id)
        
        raw_content = response.text
        
        # 构建HTML文档
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Linux.do 论坛帖子</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .topic {{ border-bottom: 1px solid #eee; padding-bottom: 20px; margin-bottom: 20px; }}
                .topic-title {{ font-size: 24px; font-weight: bold; margin-bottom: 10px; }}
                .post-content {{ line-height: 1.6; white-space: pre-wrap; }}
            </style>
        </head>
        <body>
            <div class="topic">
                <div class="topic-title">Linux.do 论坛主题 #{topic_id}</div>
            </div>
            <div class="post-content">{raw_content}</div>
        </body>
        </html>
        """
        
        return html_content.encode('utf-8'), True
    except Exception as e:
        print(f"获取原始主题内容失败: {e}")
        return None, False

def fetch_topic_by_id(topic_id):
    """直接通过topic ID获取主题内容"""
    try:
        url = f"{WEBSITE_URL}/t/{topic_id}.json"
        print(f"尝试获取主题内容: {url}")
        
        # 首先尝试使用普通请求
        response, status_code = make_api_request(url)
        
        # 如果失败，尝试使用API密钥
        if not response or status_code != 200:
            print(f"普通请求失败，尝试使用API密钥")
            response, status_code = make_api_request(url, use_api_key=True)
        
        if not response or status_code != 200:
            print(f"获取主题内容失败，状态码: {status_code}")
            return None, False
        
        try:
            topic_data = response.json()
            post_stream = topic_data.get("post_stream", {})
            posts = post_stream.get("posts", [])
            
            if posts:
                first_post = posts[0]
                title = topic_data.get("title", f"主题 #{topic_id}")
                content = first_post.get("cooked", "")
                
                # 构建HTML文档
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>{title}</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                        .topic {{ border-bottom: 1px solid #eee; padding-bottom: 20px; margin-bottom: 20px; }}
                        .topic-title {{ font-size: 24px; font-weight: bold; margin-bottom: 10px; }}
                        .post-content {{ line-height: 1.6; }}
                        .post-meta {{ color: #666; font-size: 0.9em; margin-bottom: 10px; }}
                    </style>
                </head>
                <body>
                    <div class="topic">
                        <div class="topic-title">{title}</div>
                        <div class="post-meta">
                            作者: {first_post.get("username", "匿名")} | 
                            发布于: {first_post.get("created_at", "")}
                        </div>
                    </div>
                    <div class="post-content">{content}</div>
                </body>
                </html>
                """
                
                return html_content.encode('utf-8'), True
        except Exception as e:
            print(f"解析主题JSON失败: {e}")
    except Exception as e:
        print(f"获取主题内容失败: {e}")
    
    return None, False

def try_direct_post_fetch():
    """直接尝试获取最新的帖子"""
    try:
        url = f"{WEBSITE_URL}/posts.json"
        print(f"尝试直接获取最新帖子: {url}")
        
        # 首先使用普通请求
        response, status_code = make_api_request(url)
        
        # 如果失败，尝试使用API密钥
        if not response or status_code != 200:
            print(f"普通请求失败，尝试使用API密钥")
            response, status_code = make_api_request(url, use_api_key=True)
        
        if not response or status_code != 200:
            print(f"获取最新帖子失败，状态码: {status_code}")
            return None, False
        
        try:
            data = response.json()
            latest_posts = data.get("latest_posts", [])
            
            if latest_posts:
                print(f"找到 {len(latest_posts)} 个最新帖子")
                post = latest_posts[0]
                topic_id = post.get("topic_id")
                
                if topic_id:
                    return fetch_topic_by_id(topic_id)
                else:
                    print("最新帖子中没有主题ID")
            else:
                print("未找到最新帖子")
        except json.JSONDecodeError:
            print("返回的不是有效的JSON")
    except Exception as e:
        print(f"获取最新帖子失败: {e}")
    
    return None, False

def try_rss_feed():
    """尝试获取RSS Feed，很多Discourse论坛提供这个功能"""
    try:
        # Discourse通常在这些位置提供RSS
        rss_urls = [
            f"{WEBSITE_URL}/latest.rss",
            f"{WEBSITE_URL}/top.rss",
            f"{WEBSITE_URL}/posts.rss",
            f"{WEBSITE_URL}/c/1.rss",  # 第一个分类
        ]
        
        for rss_url in rss_urls:
            print(f"尝试获取RSS feed: {rss_url}")
            response, status_code = make_api_request(rss_url)
            
            if not response or status_code != 200:
                print(f"获取RSS失败，状态码: {status_code}")
                continue
                
            # RSS是XML格式，尝试解析
            content = response.text
            
            # 如果有内容，直接创建RSS内容摘要页面
            # 我们优先选择显示RSS内容，因为这通常不会被403拦截
            if content and "<item>" in content:
                print(f"成功获取到RSS内容，长度: {len(content)} 字节")
                # 提取频道标题
                channel_title = "Linux.do 论坛"
                title_match = re.search(r"<title>(.*?)</title>", content)
                if title_match:
                    channel_title = html.escape(title_match.group(1))
                
                # 提取所有文章
                items = []
                item_blocks = re.findall(r"<item>(.*?)</item>", content, re.DOTALL)
                
                for item in item_blocks:
                    item_title = ""
                    title_match = re.search(r"<title>(.*?)</title>", item)
                    if title_match:
                        item_title = html.escape(title_match.group(1))
                    
                    item_link = ""
                    link_match = re.search(r"<link>(.*?)</link>", item)
                    if link_match:
                        item_link = html.escape(link_match.group(1))
                    
                    item_pubdate = ""
                    date_match = re.search(r"<pubDate>(.*?)</pubDate>", item)
                    if date_match:
                        item_pubdate = html.escape(date_match.group(1))
                    
                    item_desc = ""
                    desc_match = re.search(r"<description>(.*?)</description>", item, re.DOTALL)
                    if desc_match:
                        item_desc = desc_match.group(1)
                        # 移除CDATA标记
                        item_desc = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", item_desc)
                        
                        # 安全处理：
                        # 1. 保留基本HTML标签但移除脚本和样式
                        item_desc = clean_html(item_desc)
                    
                    # 尝试获取作者信息
                    item_author = "匿名用户"
                    author_match = re.search(r"<dc:creator>(.*?)</dc:creator>", item, re.DOTALL)
                    if author_match:
                        item_author = html.escape(author_match.group(1))
                    
                    # 尝试获取分类
                    item_categories = []
                    category_matches = re.findall(r"<category>(.*?)</category>", item)
                    if category_matches:
                        item_categories = [html.escape(cat) for cat in category_matches]
                    
                    items.append({
                        "title": item_title,
                        "link": item_link,
                        "date": item_pubdate,
                        "description": item_desc,
                        "author": item_author,
                        "categories": item_categories
                    })
                
                # 构建美观的HTML页面显示RSS内容 - 使用Tailwind CSS
                html_content = f"""
                <!DOCTYPE html>
                <html lang="zh-CN">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>{channel_title}</title>
                    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
                    <style>
                        /* 自定义样式与Tailwind组合 */
                        .markdown-content img {{ max-width: 100%; height: auto; }}
                        .markdown-content pre {{ overflow-x: auto; white-space: pre-wrap; }}
                        .markdown-content blockquote {{ border-left-width: 4px; }}
                        .highlight {{ background-color: rgba(255, 247, 120, 0.15); }}
                    </style>
                </head>
                <body class="bg-gray-50 dark:bg-gray-900 text-gray-800 dark:text-gray-200">
                    <div class="container mx-auto px-4 py-8 max-w-4xl">
                        <header class="mb-8">
                            <h1 class="text-3xl font-bold text-center mb-4">{channel_title}</h1>
                            <div class="bg-blue-50 dark:bg-blue-900/30 border border-blue-100 dark:border-blue-800 rounded-lg p-4 mb-6">
                                <p class="text-sm">成功获取到论坛RSS内容，共 <span class="font-semibold">{len(items)}</span> 条帖子</p>
                                <p class="text-sm">数据来源: <a href="{html.escape(rss_url)}" target="_blank" class="text-blue-600 dark:text-blue-400 hover:underline">{html.escape(rss_url)}</a></p>
                            </div>
                        </header>

                        <main>
                """
                
                # 添加每个条目的内容
                for item in items:
                    categories_html = ""
                    if item["categories"]:
                        categories_html = '<div class="flex flex-wrap gap-2 mt-2">' + ''.join([f'<span class="text-xs px-2 py-1 bg-blue-100 dark:bg-blue-800 text-blue-800 dark:text-blue-200 rounded">{cat}</span>' for cat in item["categories"]]) + '</div>'
                    
                    html_content += f"""
                        <article class="bg-white dark:bg-gray-800 rounded-lg shadow-sm mb-6 overflow-hidden">
                            <div class="p-5">
                                <h2 class="text-xl font-bold mb-3">
                                    <a href="{item["link"]}" target="_blank" class="text-blue-600 dark:text-blue-400 hover:underline">{item["title"]}</a>
                                </h2>
                                <div class="text-sm text-gray-600 dark:text-gray-400 mb-3 flex items-center">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                    </svg>
                                    <span class="mr-3">{item["author"]}</span>
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                    </svg>
                                    <span>{item["date"]}</span>
                                </div>
                                {categories_html}
                                <div class="prose dark:prose-invert max-w-none mt-4 markdown-content">
                                    {item["description"]}
                                </div>
                                <div class="mt-4 text-right">
                                    <a href="{item["link"]}" target="_blank" class="inline-flex items-center text-sm text-blue-600 dark:text-blue-400 hover:underline">
                                        查看完整内容
                                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                        </svg>
                                    </a>
                                </div>
                            </div>
                        </article>
                    """
                
                # 添加页脚
                html_content += f"""
                        </main>
                        <footer class="mt-12 border-t border-gray-200 dark:border-gray-700 pt-6 text-center text-sm text-gray-500 dark:text-gray-400">
                            <p>抓取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                            <p class="mt-2">由自动抓取工具生成 | <a href="/" class="hover:underline">返回主页</a></p>
                        </footer>
                    </div>

                    <script>
                        // 检测深色模式
                        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {{
                            document.documentElement.classList.add('dark');
                        }}
                        
                        // 为外部链接添加安全属性
                        document.addEventListener('DOMContentLoaded', () => {{
                            const externalLinks = document.querySelectorAll('a[href^="http"]');
                            externalLinks.forEach(link => {{
                                if (!link.getAttribute('rel')) {{
                                    link.setAttribute('rel', 'noopener noreferrer');
                                }}
                            }});
                        }});
                    </script>
                </body>
                </html>
                """
                
                return html_content.encode('utf-8'), True
                
            # 简单检查是否包含帖子信息
            if "<item>" in content:
                # 提取第一个帖子的链接
                link_pattern = r"<link>(.*?)</link>"
                matches = re.findall(link_pattern, content)
                
                if matches:
                    for link in matches:
                        # 尝试从链接中提取主题ID
                        topic_pattern = r"/t/[^/]+/(\d+)"
                        topic_match = re.search(topic_pattern, link)
                        
                        if topic_match:
                            topic_id = topic_match.group(1)
                            print(f"从RSS feed找到主题ID: {topic_id}")
                            return fetch_topic_by_id(topic_id)
            
            # 如果有内容但无法解析结构化信息，至少显示原始内容
            if content:
                print(f"创建RSS原始内容页面")
                html_content = f"""
                <!DOCTYPE html>
                <html lang="zh-CN">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Linux.do 论坛RSS内容</title>
                    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
                </head>
                <body class="bg-gray-50 dark:bg-gray-900 text-gray-800 dark:text-gray-200">
                    <div class="container mx-auto px-4 py-8 max-w-4xl">
                        <h1 class="text-3xl font-bold text-center mb-6">Linux.do 论坛RSS内容</h1>
                        <div class="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-4 overflow-auto">
                            <pre class="text-sm whitespace-pre-wrap break-words">{html.escape(content)}</pre>
                        </div>
                        <footer class="mt-12 border-t border-gray-200 dark:border-gray-700 pt-6 text-center text-sm text-gray-500 dark:text-gray-400">
                            <p>抓取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                            <p class="mt-2">由自动抓取工具生成 | <a href="/" class="hover:underline">返回主页</a></p>
                        </footer>
                    </div>

                    <script>
                        // 检测深色模式
                        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {{
                            document.documentElement.classList.add('dark');
                        }}
                    </script>
                </body>
                </html>
                """
                return html_content.encode('utf-8'), True
                
    except Exception as e:
        print(f"获取RSS feed失败: {e}")
    
    return None, False

def clean_html(html_content):
    """
    清理HTML内容，移除潜在的危险标签，但保留基本格式
    """
    if not html_content:
        return ""
    
    # 移除所有脚本标签
    html_content = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', html_content)
    
    # 移除所有样式标签
    html_content = re.sub(r'<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>', '', html_content)
    
    # 移除所有iframe
    html_content = re.sub(r'<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>', '', html_content)
    
    # 移除所有事件属性（例如onclick, onload等）
    html_content = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', '', html_content)
    
    # 移除所有javascript:协议
    html_content = re.sub(r'javascript:', 'void(0);', html_content)
    
    # 修复相对链接路径
    html_content = re.sub(r'href=(["\'])/', f'href=\\1{WEBSITE_URL}/', html_content)
    html_content = re.sub(r'src=(["\'])/', f'src=\\1{WEBSITE_URL}/', html_content)
    
    return html_content

def try_all_api_endpoints():
    """尝试所有可能的API端点"""
    for endpoint in API_ENDPOINTS:
        try:
            print(f"尝试API端点: {endpoint}")
            
            # 首先使用普通请求
            response, status_code = make_api_request(endpoint)
            
            # 如果失败，尝试使用API密钥
            if not response or status_code != 200:
                print(f"普通请求失败，尝试使用API密钥")
                response, status_code = make_api_request(endpoint, use_api_key=True)
            
            if not response or status_code != 200:
                print(f"端点 {endpoint} 失败，状态码: {status_code}")
                continue
                
            print(f"端点 {endpoint} 成功，状态码: 200")
            # 尝试解析JSON响应
            try:
                json_data = response.json()
                
                # 检查是否为posts.json响应
                if "latest_posts" in json_data and json_data["latest_posts"]:
                    posts = json_data["latest_posts"]
                    if posts:
                        print(f"在 {endpoint} 找到 {len(posts)} 个帖子")
                        topic_id = posts[0].get("topic_id")
                        if topic_id:
                            return fetch_topic_by_id(topic_id)
                
                # 查找主题列表
                if "topic_list" in json_data and "topics" in json_data["topic_list"] and json_data["topic_list"]["topics"]:
                    topics = json_data["topic_list"]["topics"]
                    if topics:
                        print(f"在 {endpoint} 找到 {len(topics)} 个主题")
                        topic_id = topics[0].get("id")
                        if topic_id:
                            return fetch_topic_by_id(topic_id)
                elif "topics" in json_data and json_data["topics"]:
                    topics = json_data["topics"]
                    print(f"在 {endpoint} 找到 {len(topics)} 个主题")
                    topic_id = topics[0].get("id")
                    if topic_id:
                        return fetch_topic_by_id(topic_id)
                
                # 查找分类列表，获取第一个分类的主题
                if "categories" in json_data and json_data["categories"]:
                    categories = json_data["categories"]
                    category_id = categories[0].get("id")
                    if category_id:
                        return try_category_endpoint(category_id)
            except json.JSONDecodeError:
                print(f"端点 {endpoint} 返回的不是有效的JSON")
        except Exception as e:
            print(f"尝试API端点 {endpoint} 失败: {e}")
    
    # 如果所有API都失败，尝试直接从HTML中获取
    return fetch_latest_posts_from_html()

def try_category_endpoint(category_id):
    """尝试获取特定分类的主题"""
    try:
        endpoint = f"{WEBSITE_URL}/c/{category_id}.json"
        print(f"尝试获取分类 {category_id} 的主题: {endpoint}")
        
        # 首先使用普通请求
        response, status_code = make_api_request(endpoint, referrer=f"{WEBSITE_URL}/c/{category_id}")
        
        # 如果失败，尝试使用API密钥
        if not response or status_code != 200:
            print(f"普通请求失败，尝试使用API密钥")
            response, status_code = make_api_request(endpoint, use_api_key=True)
        
        if not response or status_code != 200:
            print(f"获取分类主题失败，状态码: {status_code}")
            return None, False
            
        try:
            json_data = response.json()
            if "topic_list" in json_data and "topics" in json_data["topic_list"] and json_data["topic_list"]["topics"]:
                topics = json_data["topic_list"]["topics"]
                if topics:
                    print(f"在分类 {category_id} 中找到 {len(topics)} 个主题")
                    topic_id = topics[0].get("id")
                    if topic_id:
                        return fetch_topic_by_id(topic_id)
        except json.JSONDecodeError:
            print(f"分类端点返回的不是有效的JSON")
    except Exception as e:
        print(f"尝试获取分类主题失败: {e}")
    
    return None, False

def fetch_discourse_content():
    """尝试多种方法获取Discourse内容"""
    print("尝试多种方法获取Discourse内容")
    
    # 首先尝试RSS feed（最不容易被阻挡）
    content, success = try_rss_feed()
    if success and content:
        return content, True
    
    # 然后尝试直接获取最新帖子
    content, success = try_direct_post_fetch()
    if success and content:
        return content, True
    
    # 然后尝试所有API端点
    content, success = try_all_api_endpoints()
    if success and content:
        return content, True
    
    # 如果都失败，尝试获取主页并解析内容
    print("所有API端点尝试失败，尝试直接抓取主页内容")
    content, success = fetch_latest_posts_from_html()
    if success and content:
        return content, True
    
    # 最后的备选方案：创建一个简单的说明页面，表示无法获取内容
    error_html = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>无法获取Linux.do内容</title>
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    </head>
    <body class="bg-gray-50 dark:bg-gray-900 text-gray-800 dark:text-gray-200">
        <div class="container mx-auto px-4 py-8 flex items-center justify-center min-h-screen">
            <div class="bg-white dark:bg-gray-800 rounded-lg shadow-md p-8 max-w-2xl w-full">
                <div class="flex justify-center mb-6">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                </div>
                <h1 class="text-2xl font-bold text-center mb-4">无法获取Linux.do论坛内容</h1>
                <div class="space-y-4">
                    <p>尝试了多种方法但未能成功获取Linux.do论坛的内容。可能的原因包括：</p>
                    <ul class="list-disc pl-5 space-y-2">
                        <li>服务器拒绝了我们的请求（403错误）</li>
                        <li>网站需要登录或认证才能访问</li>
                        <li>网站结构发生了变化</li>
                        <li>网络连接问题</li>
                    </ul>
                    <div class="bg-blue-50 dark:bg-blue-900/30 rounded p-4 mt-6">
                        <p class="text-sm">截图时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    </div>
                    <p class="text-center mt-6">
                        您仍然可以通过直接访问 
                        <a href="https://linux.do" class="text-blue-600 dark:text-blue-400 hover:underline" target="_blank" rel="noopener noreferrer">https://linux.do</a> 
                        来查看论坛内容。
                    </p>
                </div>
                <div class="mt-8 text-center">
                    <a href="/" class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded">返回主页</a>
                </div>
            </div>
        </div>

        <script>
            // 检测深色模式
            if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {{
                document.documentElement.classList.add('dark');
            }}
        </script>
    </body>
    </html>
    """
    
    return error_html.encode('utf-8'), True

def take_single_screenshot():
    """执行单次截图，由定时器调用"""
    global screenshots, html_files
    
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
        html_path = HTML_DIR / f"snapshot_{timestamp}.html"  # HTML文件路径
        
        screenshot_success = False
        html_success = False
        
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
            
            # 获取linux.do网站内容
            try:
                # 使用多种方法尝试获取内容
                html_content, success = fetch_discourse_content()
                
                if success and html_content:
                    # 保存HTML内容到文件
                    with open(html_path, "wb") as f:
                        f.write(html_content)
                    html_success = True
                    
                    # 更新HTML文件列表
                    html_files.append({
                        "filename": f"snapshot_{timestamp}.html",
                        "path": f"screenshots/html/snapshot_{timestamp}.html",
                        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "timestamp": timestamp
                    })
                    
                    # 按时间倒序排序
                    html_files.sort(key=lambda x: x["timestamp"], reverse=True)
                    
                    # 如果超过最大数量，删除最早的HTML文件
                    if len(html_files) > MAX_SCREENSHOTS:
                        oldest = html_files.pop(-1)
                        oldest_file = HTML_DIR / oldest["filename"]
                        
                        if os.path.exists(oldest_file):
                            os.remove(oldest_file)
                        
                        print(f"删除旧HTML文件: {oldest['filename']}")
                    
                    print(f"抓取网页完成: {timestamp}")
                else:
                    print(f"抓取网页失败")
            except Exception as e:
                print(f"抓取网页过程出错: {e}")
                
                # 清理可能部分创建的HTML文件
                if os.path.exists(html_path):
                    try:
                        os.remove(html_path)
                    except Exception:
                        pass
            
            # 更新截屏列表
            screenshots.append({
                "filename": f"screenshot_{timestamp}.png",
                "thumbnail": f"screenshots/thumbnails/thumbnail_{timestamp}.png",
                "html": f"screenshots/html/snapshot_{timestamp}.html" if html_success else None,
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

@app.get("/api/html/{timestamp}")
async def get_html_snapshot(timestamp: str):
    """获取特定的HTML快照文件"""
    html_file_path = HTML_DIR / f"snapshot_{timestamp}.html"
    if os.path.exists(html_file_path):
        return FileResponse(html_file_path, media_type="text/html")
    return JSONResponse(status_code=404, content={"error": "HTML快照不存在"})

@app.get("/api/html_files")
async def get_html_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(PAGE_SIZE, ge=1, le=100),
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    exact_time: Optional[str] = None
):
    """API 获取HTML文件信息，支持分页和时间筛选"""
    filtered_html_files = html_files.copy()
    
    # 时间筛选
    if exact_time:
        filtered_html_files = [h for h in filtered_html_files if h["timestamp"] == exact_time]
    else:
        if start_time:
            filtered_html_files = [h for h in filtered_html_files if h["timestamp"] >= start_time]
        if end_time:
            filtered_html_files = [h for h in filtered_html_files if h["timestamp"] <= end_time]
    
    # 计算总页数和总数量
    total_count = len(filtered_html_files)
    total_pages = (total_count + page_size - 1) // page_size
    
    # 分页处理
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_count)
    
    # 返回分页后的数据及分页信息
    return {
        "items": filtered_html_files[start_idx:end_idx],
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

@app.get("/api/latest")
async def get_latest_screenshot():
    """获取最新的一张截屏"""
    if not screenshots:
        return JSONResponse(status_code=404, content={"error": "暂无截屏"})
    
    # 由于screenshots已经按时间戳倒序排序，第一个就是最新的
    latest = screenshots[0]
    return {
        "screenshot": latest,
        "direct_url": f"/api/screenshot/{latest['timestamp']}",
        "html_url": f"/api/html/{latest['timestamp']}" if latest.get("html") else None
    }

@app.get("/api/latest_html")
async def get_latest_html():
    """获取最新的HTML快照"""
    if not html_files:
        return JSONResponse(status_code=404, content={"error": "暂无HTML快照"})
    
    # 由于html_files已经按时间戳倒序排序，第一个就是最新的
    latest = html_files[0]
    return {
        "html": latest,
        "direct_url": f"/api/html/{latest['timestamp']}"
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