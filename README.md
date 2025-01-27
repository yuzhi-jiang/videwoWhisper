# 视频字幕提取工具

这是一个基于 OpenAI Whisper 的视频字幕提取工具，可以自动从视频文件中提取音频并生成字幕文件。支持智能翻译和自定义词典替换。

## 功能特点

- 自动从视频文件中提取音频
- 使用 Whisper large-v3-turbo 模型进行语音识别
- 支持生成 SRT 格式的字幕文件
- 支持多语言识别和翻译
- 智能上下文翻译，提高翻译质量
- 支持自定义替换词典
- 支持双语字幕输出
- 自动清理临时文件
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

## 配置说明

### 配置文件
程序使用 `config.json` 进行配置，支持以下配置项：

```json
{
    "api": {
        "openai_api_key": "your_api_key_here",
        "openai_api_base": "https://api.deepseek.com/v1"
    },
    "translation": {
        "default_model": "deepseek-chat",
        "context_window": 3,
        "max_workers": 5
    },
    "word_dict": {
        "path": "word_dict.txt",
        "enabled": true
    }
}
```

### 配置项说明
- `api`: API相关配置
  - `openai_api_key`: API密钥
  - `openai_api_base`: API基础URL
- `translation`: 翻译相关配置
  - `default_model`: 默认使用的模型
  - `context_window`: 上下文窗口大小
  - `max_workers`: 最大并发翻译数
- `word_dict`: 词典相关配置
  - `path`: 词典文件路径
  - `enabled`: 是否启用词典

### 自定义词典
词典文件（默认为 `word_dict.txt`）使用以下格式：
```
原文->替换文
人工智能->AI
深度学习->Deep Learning
```

每行一个替换规则，使用 `->` 分隔原文和替换文。

## 使用方法

1. 基本用法：
```python
python app.py
```

2. 访问Web界面：
   - 打开浏览器访问 `http://localhost:5000`
   - 上传视频文件
   - 选择目标语言和其他选项
   - 等待处理完成后下载字幕文件

## 翻译功能说明

1. 上下文翻译
   - 翻译时会考虑前后文（默认各3句）
   - 提高翻译的连贯性和准确性

2. 自定义词典
   - 支持特定术语的精确替换
   - 可以保持专业术语的一致性
   - 词典规则会在翻译后自动应用

3. 双语字幕
   - 可选择保留原文
   - 支持生成双语字幕文件

## 注意事项

1. 首次运行时会自动下载 Whisper 模型文件
2. 建议使用 GPU 进行加速，可以显著提高处理速度
3. 生成的字幕文件将与输入视频同名，格式为 .srt
4. API密钥可以通过环境变量或配置文件设置
5. 确保词典文件使用UTF-8编码

## 日志说明

程序运行时会输出详细的日志信息，包括：
- 配置加载状态
- 模型加载状态
- 转录进度
- 翻译状态
- 词典应用情况
- 错误信息（如果有） 