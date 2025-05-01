@echo off
setlocal enabledelayedexpansion

echo 截屏服务启动工具

:: 检查是否存在便携式Python环境
if not exist portable_python (
    echo 首次运行，正在准备便携式环境...
    
    :: 创建下载目录
    mkdir downloads 2>nul
    
    :: 下载便携式Python (如果没有)
    if not exist downloads\python_embed.zip (
        echo 正在下载便携式Python...
        powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip' -OutFile 'downloads\python_embed.zip'"
    )
    
    :: 下载pip (如果没有)
    if not exist downloads\get-pip.py (
        echo 正在下载pip安装程序...
        powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'downloads\get-pip.py'"
    )
    
    :: 解压Python
    echo 正在解压Python...
    powershell -Command "Expand-Archive -Path 'downloads\python_embed.zip' -DestinationPath 'portable_python' -Force"
    
    :: 修改python310._pth文件以启用导入功能
    echo 配置Python环境...
    powershell -Command "(Get-Content 'portable_python\python310._pth') -replace '#import site', 'import site' | Set-Content 'portable_python\python310._pth'"
    
    :: 安装pip
    echo 正在安装pip...
    portable_python\python.exe downloads\get-pip.py
    
    :: 安装所需依赖
    echo 正在安装依赖项...
    portable_python\Scripts\pip.exe install fastapi uvicorn python-multipart pillow pyautogui jinja2
)

:: 启动应用
echo 正在启动截屏服务...
portable_python\python.exe -m app.main

:: 如果应用意外关闭，保持窗口打开
pause 