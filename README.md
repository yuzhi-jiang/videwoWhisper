# 视频字幕提取工具

这是一个基于 OpenAI Whisper 的视频字幕提取工具，可以自动从视频文件中提取音频并生成字幕文件。

## 功能特点

- 自动从视频文件中提取音频
- 使用 Whisper large-v3-turbo 模型进行语音识别
- 支持生成 SRT 格式的字幕文件
- 支持多语言识别（默认中文）
- 自动清理临时音频文件
- 详细的日志记录

## 环境要求

- Python 3.8+
- FFmpeg
- CUDA（可选，用于 GPU 加速）

## 安装步骤

1. 克隆仓库：
```bash
git clone [仓库地址]
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 确保已安装 FFmpeg

## 使用方法

1. 基本用法：
```python
python genSrt.py
```

2. 修改配置：
在 `genSrt.py` 中设置以下参数：
- `video_file`：输入视频文件路径
- `output_dir`：字幕输出目录
- `language`：识别语言（默认为中文）

## 参数说明

- `video_file`：输入视频文件路径
- `output_audio_file`：临时音频文件路径（自动生成）
- `output_dir`：字幕文件输出目录
- `language`：识别语言（默认为"Chinese"）
- `output_format`：输出格式（默认为"srt"）
- `device`：运行设备（可选择"cuda"用于 GPU 加速）

## 注意事项

1. 首次运行时会自动下载 Whisper 模型文件
2. 建议使用 GPU 进行加速，可以显著提高处理速度
3. 生成的字幕文件将与输入视频同名，格式为 .srt

## 日志说明

程序运行时会输出详细的日志信息，包括：
- 模型加载状态
- 转录进度
- 临时文件处理情况
- 错误信息（如果有） 