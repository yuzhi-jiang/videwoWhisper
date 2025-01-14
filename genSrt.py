import ffmpeg
import whisper
import logging
import whisper.utils
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")



def extract_audio(video_file, output_audio_file):
    # 使用 ffmpeg 提取音频
    ffmpeg.input(video_file).output(output_audio_file, q=0, map='a').run()


def extract_subtitles(audio_file, output_dir, language='Chinese',output_format = "srt", device=None):
    # 加载 whisper 模型
    model = whisper.load_model("large-v3-turbo", device=device)
    logging.info("Model loaded successfully.")
    
    # 提取字幕
    logging.info("Starting transcription...")
    # 设置转录选项,生成srt格式字幕
    transcribe_options = {
        "task": "transcribe",
        "language": language,
        "verbose": True,
        "word_timestamps": True,  # 启用词级时间戳
    }
    result = model.transcribe(audio_file,**transcribe_options)

    logging.info("Transcription completed.")
    

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

