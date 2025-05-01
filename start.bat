@echo off
echo 正在启动截屏服务...

:: 激活虚拟环境
call venv\Scripts\activate.bat

:: 启动应用
python -m app.main

:: 如果应用意外关闭，保持窗口打开
pause 