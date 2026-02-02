#!/bin/bash

# AI 旅行规划助手 - 快速启动脚本 (Linux/Mac)

set -e

echo "========================================"
echo "   AI 旅行规划助手 - 启动脚本"
echo "========================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未检测到 Python，请先安装 Python 3.10+"
    exit 1
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ 错误: 未检测到 Node.js，请先安装 Node.js 16+"
    exit 1
fi

echo "✅ Python 和 Node.js 已安装"
echo ""

# 菜单函数
show_menu() {
    echo ""
    echo "请选择操作:"
    echo "1. 安装依赖"
    echo "2. 启动后端服务 (8000 端口)"
    echo "3. 启动前端开发服务 (5173 端口)"
    echo "4. 启动完整应用 (后台启动)"
    echo "5. 使用 Docker Compose 启动"
    echo "6. 清理临时文件"
    echo "7. 退出"
    echo ""
    read -p "请输入选择 (1-7): " choice
    
    case $choice in
        1) install_deps ;;
        2) start_backend ;;
        3) start_frontend ;;
        4) start_full ;;
        5) start_docker ;;
        6) clean_files ;;
        7) exit 0 ;;
        *) echo "❌ 无效的选择"; show_menu ;;
    esac
}

# 安装依赖
install_deps() {
    echo ""
    echo "📦 安装后端依赖..."
    cd backend
    pip3 install -r requirements.txt
    cd ..
    
    echo ""
    echo "📦 安装前端依赖..."
    cd frontend
    npm install
    cd ..
    
    echo ""
    echo "✅ 所有依赖安装成功！"
    show_menu
}

# 启动后端
start_backend() {
    echo ""
    echo "🚀 启动后端服务..."
    echo "服务地址: http://localhost:8000"
    echo "API 文档: http://localhost:8000/docs"
    echo "按 Ctrl+C 停止服务"
    echo ""
    cd backend
    python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
    cd ..
}

# 启动前端
start_frontend() {
    echo ""
    echo "🚀 启动前端开发服务..."
    echo "服务地址: http://localhost:5173"
    echo "按 Ctrl+C 停止服务"
    echo ""
    cd frontend
    npm run dev
    cd ..
}

# 启动完整应用
start_full() {
    echo ""
    echo "🚀 启动完整应用..."
    echo ""
    
    # 启动后端（后台）
    echo "启动后端服务..."
    cd backend
    python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload > ../backend.log 2>&1 &
    BACKEND_PID=$!
    cd ..
    
    echo "✅ 后端服务已启动 (PID: $BACKEND_PID)"
    
    sleep 2
    
    # 启动前端
    echo "启动前端服务..."
    cd frontend
    npm run dev
    cd ..
    
    echo ""
    echo "后端服务 PID: $BACKEND_PID"
    echo "要停止后端服务，运行: kill $BACKEND_PID"
}

# Docker Compose 启动
start_docker() {
    echo ""
    echo "🐳 使用 Docker Compose 启动..."
    echo ""
    
    if ! command -v docker-compose &> /dev/null; then
        echo "❌ 错误: 未检测到 Docker Compose"
        echo "请先安装 Docker Desktop"
        show_menu
        return
    fi
    
    echo "启动容器..."
    docker-compose up -d
    
    echo ""
    echo "✅ 容器已启动！"
    echo "后端服务: http://localhost:8000"
    echo "前端应用: http://localhost"
    echo ""
    echo "查看日志:"
    echo "  docker-compose logs -f"
    echo ""
    echo "停止容器:"
    echo "  docker-compose down"
    echo ""
    show_menu
}

# 清理文件
clean_files() {
    echo ""
    echo "🧹 清理临时文件..."
    echo ""
    
    # 清理 Python 缓存
    echo "清理后端缓存..."
    find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find backend -type f -name "*.pyc" -delete 2>/dev/null || true
    
    # 清理 Node 缓存
    if [ -d "frontend/node_modules" ]; then
        echo "清理前端依赖 (这可能需要一些时间)..."
        rm -rf frontend/node_modules
    fi
    
    if [ -d "frontend/dist" ]; then
        echo "清理前端构建文件..."
        rm -rf frontend/dist
    fi
    
    echo ""
    echo "✅ 清理完成！"
    show_menu
}

# 主程序
show_menu
