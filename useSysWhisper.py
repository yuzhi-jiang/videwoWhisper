import subprocess

def extract_audio(video_file, output_audio_file):
    # 使用 ffmpeg 提取音频
    command = [
        'ffmpeg',
        # '-hwaccel', 'cuda',  # 使用硬件加速（可选）
        '-i', video_file,   # 输入视频文件
        '-q:a', '0',        # 音频质量（0 表示最高质量）
        '-map', 'a',        # 仅提取音频流
        # '-c:a', 'aac',      # 音频编码格式
        output_audio_file   # 输出音频文件
    ]
    
    # 执行命令
    subprocess.run(command, check=True)

def extract_subtitles(audio_file, output_dir, language='Chinese', device='cuda'):
    # 使用 whisper 提取字幕
    command = [
        'whisper',
        audio_file,
        '--language', language,
        '--output_dir', output_dir,
        '--device', device
    ]
    subprocess.run(command, check=True)

output_dir = '.'              # 字幕输出目录

# 示例用法a
# video_file = 'a.mp4'  # 输入视频文件a
# output_audio_file = 'a.mp3'  # 输出音频文件
# extract_audio(video_file, output_audio_file)
# extract_subtitles(output_audio_file, output_dir)



def genSrt(video_file, output_audio_file, output_dir):
    extract_audio(video_file, output_audio_file)
    extract_subtitles(output_audio_file, output_dir)