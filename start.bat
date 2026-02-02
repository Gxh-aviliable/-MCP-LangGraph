@echo off
REM AI 旅行规划助手 - 快速启动脚本 (Windows)

setlocal enabledelayedexpansion

echo ========================================
echo    AI 旅行规划助手 - 启动脚本
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未检测到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

REM 检查 Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未检测到 Node.js，请先安装 Node.js 16+
    pause
    exit /b 1
)

echo ✅ Python 和 Node.js 已安装
echo.

REM 设置菜单
:menu
echo.
echo 请选择操作:
echo 1. 安装依赖
echo 2. 启动后端服务 (8000 端口)
echo 3. 启动前端开发服务 (5173 端口)
echo 4. 启动完整应用 (需要两个终端)
echo 5. 使用 Docker Compose 启动 (需要 Docker)
echo 6. 清理临时文件
echo 7. 退出
echo.

set /p choice="请输入选择 (1-7): "

if "%choice%"=="1" goto install
if "%choice%"=="2" goto backend
if "%choice%"=="3" goto frontend
if "%choice%"=="4" goto full
if "%choice%"=="5" goto docker
if "%choice%"=="6" goto clean
if "%choice%"=="7" goto end

echo ❌ 无效的选择，请重新输入
goto menu

:install
echo.
echo 📦 安装后端依赖...
cd backend
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ 后端依赖安装失败
    pause
    cd ..
    goto menu
)
cd ..

echo.
echo 📦 安装前端依赖...
cd frontend
call npm install
if errorlevel 1 (
    echo ❌ 前端依赖安装失败
    pause
    cd ..
    goto menu
)
cd ..

echo.
echo ✅ 所有依赖安装成功！
pause
goto menu

:backend
echo.
echo 🚀 启动后端服务...
echo 服务地址: http://localhost:8000
echo API 文档: http://localhost:8000/docs
echo.
cd backend
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
cd ..
pause
goto menu

:frontend
echo.
echo 🚀 启动前端开发服务...
echo 服务地址: http://localhost:5173
echo.
cd frontend
call npm run dev
cd ..
pause
goto menu

:full
echo.
echo 🚀 启动完整应用...
echo.
echo 后端服务将在新窗口中启动
echo 请在后端启动后，手动启动前端
echo.
echo 启动后端... (需要保持窗口打开)
cd backend
start cmd /k "python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"
cd ..
echo.
echo ✅ 后端已启动，现在启动前端...
timeout /t 3 /nobreak
cd frontend
call npm run dev
cd ..
pause
goto menu

:docker
echo.
echo 🐳 使用 Docker Compose 启动...
echo.

docker-compose version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未检测到 Docker Compose
    echo 请先安装 Docker Desktop
    pause
    goto menu
)

echo 启动容器...
docker-compose up -d

if errorlevel 1 (
    echo ❌ Docker Compose 启动失败
    pause
    goto menu
)

echo.
echo ✅ 容器已启动！
echo 后端服务: http://localhost:8000
echo 前端应用: http://localhost
echo.
echo 查看日志:
echo   docker-compose logs -f
echo.
echo 停止容器:
echo   docker-compose down
echo.
pause
goto menu

:clean
echo.
echo 🧹 清理临时文件...
echo.

REM 清理 Python 缓存
if exist backend\__pycache__ (
    echo 清理后端缓存...
    rmdir /s /q backend\__pycache__
)

REM 清理 Node 缓存
if exist frontend\node_modules (
    echo 清理前端依赖 (这可能需要一些时间)...
    rmdir /s /q frontend\node_modules
)

if exist frontend\dist (
    echo 清理前端构建文件...
    rmdir /s /q frontend\dist
)

echo ✅ 清理完成！
pause
goto menu

:end
echo.
echo 👋 再见！
echo.
pause
exit /b 0
