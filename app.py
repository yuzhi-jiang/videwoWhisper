from flask import Flask, render_template, request, send_file, jsonify
import os
from werkzeug.utils import secure_filename
import logging
import time
from task_processor import TaskProcessor

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1GB 限制

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 创建任务处理器
task_processor = TaskProcessor()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status/<task_id>')
def get_status(task_id):
    status = task_processor.get_status(task_id)
    if status:
        return jsonify(status)
    return jsonify({'error': '任务不存在'}), 404

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

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'video' not in request.files:
        return jsonify({'error': '没有上传文件'}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400

    if not file.filename.lower().endswith(('.mp4', '.avi', '.mkv', '.mov')):
        return jsonify({'error': '不支持的文件格式'}), 400

    try:
        # 生成任务ID
        task_id = str(int(time.time() * 1000))

        # 保存视频文件
        filename = secure_filename(file.filename)
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(video_path)

        # 添加任务到处理队列
        task_processor.add_task(task_id, video_path, app.config['UPLOAD_FOLDER'])

        return jsonify({
            'task_id': task_id,
            'message': '任务已添加到队列'
        })

    except Exception as e:
        logging.error(f"处理过程中出错: {str(e)}")
        return jsonify({'error': f'处理失败: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000) 