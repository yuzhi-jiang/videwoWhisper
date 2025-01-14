import ffmpeg
import whisper
import logging
import whisper.utils

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 支持的模型列表
AVAILABLE_MODELS = {
    'tiny': {'name': 'tiny', 'description': '最小模型，速度最快，准确度较低'},
    'base': {'name': 'base', 'description': '基础模型，速度较快，准确度一般'},
    'small': {'name': 'small', 'description': '小型模型，速度和准确度均衡'},
    'medium': {'name': 'medium', 'description': '中型模型，准确度较高，速度较慢'},
    'large-v3': {'name': 'large-v3', 'description': '大型模型，最高准确度，速度最慢'},
    'large-v3-turbo': {'name': 'large-v3-turbo', 'description': '大型模型，在保留准确度的同时，速度更快'},
}

def get_available_models():
    """获取可用的模型列表"""
    return AVAILABLE_MODELS

def extract_audio(video_file, output_audio_file):
    # 使用 ffmpeg 提取音频
    ffmpeg.input(video_file).output(output_audio_file, q=0, map='a').run()

def extract_subtitles(audio_file, output_dir, language='Chinese', output_format="srt", device=None, model_name='large-v3-turbo'):
    """
    提取字幕
    :param audio_file: 音频文件路径
    :param output_dir: 输出目录
    :param language: 语言
    :param output_format: 输出格式
    :param device: 设备（cuda/cpu）
    :param model_name: 模型名称
    """
    # 检查模型是否支持
    if model_name not in AVAILABLE_MODELS:
        raise ValueError(f"不支持的模型: {model_name}")

    # 加载 whisper 模型
    logging.info(f"正在加载模型 {model_name}...")

    model = whisper.load_model(model_name,download_root='./models', device=device)
    logging.info("模型加载成功。")
    
    # 提取字幕
    logging.info("开始转录...")
    # 设置转录选项,生成srt格式字幕
    transcribe_options = {
        "task": "transcribe",
        "language": language,
        "verbose": True,
        "word_timestamps": True,  # 启用词级时间戳
    }
    result = model.transcribe(audio_file, **transcribe_options)
    logging.info("转录完成。")

    file_name = get_file_name(audio_file)
    writer = whisper.utils.get_writer(output_format, output_dir)
    writer(result, file_name)

def get_file_name(file_path):
    return file_path.split('/')[-1].split('.')[0]

# 示例用法
video_file = 'a.mp4'          # 输入视频文件
output_audio_file = get_file_name(video_file)+'.mp3'   # 输出音频文件
output_dir = '.'              # 字幕输出目录


# 删除临时音频文件
import os
def genSrt(video_file, output_audio_file, output_dir):
    # 提取音频
    extract_audio(video_file, output_audio_file)

    # 提取字幕
    extract_subtitles(output_audio_file, output_dir)
    try:
        os.remove(output_audio_file)
        logging.info(f"临时音频文件 {output_audio_file} 已删除")
    except OSError as e:
        logging.error(f"删除临时音频文件时出错: {e}")

