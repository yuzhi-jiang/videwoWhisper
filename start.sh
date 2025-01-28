#!/bin/bash

# 检查是否安装了conda
if command -v conda >/dev/null 2>&1; then
    echo "检测到conda已安装"
    
    # 初始化conda（确保可以在脚本中使用conda命令）
    source $(conda info --base)/etc/profile.d/conda.sh
    
    # 检查是否存在video环境
    if conda env list | grep -q "video"; then
        echo "激活conda video环境"
        conda activate video
    else
        echo "conda video环境不存在，正在创建..."
        # 使用video_env.yml创建环境（如果文件存在）
        if [ -f "video_env.yml" ]; then
            conda env create -f video_env.yml
            conda activate video
        else
            # 如果没有yml文件，创建基本环境
            conda create -n video python=3.12 -y
            conda activate video
            # 安装必要的包
            pip install -r requirements.txt
        fi
    fi
else
    echo "未检测到conda，使用Python虚拟环境"
    # 检查并创建Python虚拟环境
    if [ ! -d "video_env" ]; then
        echo "创建Python虚拟环境..."
        python -m venv video_env
    fi
    source video_env/bin/activate
    
    # 安装依赖（如果requirements.txt存在）
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    fi
fi

# 设置Python路径
export PYTHONPATH="."

# 启动Flask应用
nohup python app.py > app.log 2>&1 &

# 获取进程ID并保存
echo $! > app.pid

echo "Flask应用已在后台启动，PID: $!"
echo "访问 http://localhost:5000"
echo "查看日志: tail -f app.log" 