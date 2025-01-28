#!/bin/bash

# 检查PID文件是否存在
if [ -f "app.pid" ]; then
    PID=$(cat app.pid)
    
    # 检查进程是否仍在运行
    if ps -p $PID > /dev/null; then
        echo "正在停止Flask应用 (PID: $PID)..."
        kill $PID
        rm app.pid
        echo "Flask应用已停止"
    else
        echo "进程已不存在"
        rm app.pid
    fi
else
    # 如果PID文件不存在，尝试查找并终止所有相关的Python进程
    PIDS=$(pgrep -f "python app.py")
    if [ ! -z "$PIDS" ]; then
        echo "找到以下Flask应用进程："
        echo $PIDS
        echo "正在停止所有Flask应用进程..."
        kill $PIDS
        echo "所有Flask应用已停止"
    else
        echo "未找到运行中的Flask应用"
    fi
fi 