from flask import Flask, render_template, request, send_file, jsonify
import os
from werkzeug.utils import secure_filename
import logging
import time
from task_processor import TaskProcessor

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1GB 限制

# OpenAI API 配置
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 'your_openai_api_key')
OPENAI_API_BASE = os.getenv('OPENAI_API_BASE', 'https://api.deepseek.com/v1')  # 可选，用于自定义API端点

# 支持的文件类型
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov'}
ALLOWED_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.aac', '.flac'}

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 创建任务处理器
task_processor = TaskProcessor(
    openai_api_key=OPENAI_API_KEY,
    openai_api_base=OPENAI_API_BASE,
    num_workers=2
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status/<task_id>')
def get_status(task_id):
    status = task_processor.get_status(task_id)
    if status:
        return jsonify(status)
    return jsonify({'error': '任务不存在'}), 404

@app.route('/status/all')
def get_all_status():
    """获取所有任务的状态"""
    return jsonify(task_processor.get_all_status())

@app.route('/download/<task_id>')
def download_file(task_id):
    status = task_processor.get_status(task_id)
    if not status or status['status'] != 'completed':
        return jsonify({'error': '文件不存在或任务未完成'}), 404
    
    srt_file = status['srt_file']
    if not os.path.exists(srt_file):
        return jsonify({'error': '字幕文件不存在'}), 404
    
    return send_file(
        srt_file,
        as_attachment=True,
        download_name=os.path.basename(srt_file)
    )

def get_file_type(filename):
    """判断文件类型"""
    ext = os.path.splitext(filename.lower())[1]
    if ext in ALLOWED_VIDEO_EXTENSIONS:
        return 'video'
    elif ext in ALLOWED_AUDIO_EXTENSIONS:
        return 'audio'
    return None

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': '没有上传文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400

    # 检查文件类型
    file_type = get_file_type(file.filename)
    if not file_type:
        return jsonify({'error': '不支持的文件格式'}), 400

    try:
        # 生成任务ID
        task_id = str(int(time.time() * 1000))

        # 保存文件
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # 获取翻译设置
        target_lang = request.form.get('target_lang')
        keep_original = request.form.get('keep_original', 'false').lower() == 'true'

        # 添加任务到处理队列
        task_processor.add_task(
            task_id=task_id,
            file_path=file_path,
            output_dir=app.config['UPLOAD_FOLDER'],
            file_type=file_type,
            target_lang=target_lang,
            keep_original=keep_original
        )

        return jsonify({
            'task_id': task_id,
            'message': '任务已添加到队列',
            'file_type': file_type
        })

    except Exception as e:
        logging.error(f"处理过程中出错: {str(e)}")
        return jsonify({'error': f'处理失败: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=False, port=5000) 