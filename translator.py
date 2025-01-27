import os
import json
import requests
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from config_manager import ConfigManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class Translator:
    def __init__(self, api_key, api_base=None):
        self.api_key = api_key
        self.api_base = api_base
        self.max_workers = 5  # 设置最大并发数
        self.word_dict = {}  # 初始化替换词典
        
    def set_word_dict(self, dict_path):
        """
        设置替换词典
        :param dict_path: 词典文件路径，格式为每行: 原文->替换文
        """
        try:
            with open(dict_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if '->' in line:
                        source, target = line.split('->', 1)
                        self.word_dict[source.strip()] = target.strip()
            logging.info(f"成功加载词典，共 {len(self.word_dict)} 个替换规则")
        except Exception as e:
            logging.error(f"加载词典失败: {str(e)}")
            raise

    def apply_word_dict(self, text):
        """
        应用词典替换
        """
        for source, target in self.word_dict.items():
            text = text.replace(source, target)
        return text

    def translate_srt(self, srt_file, target_lang, keep_original=False, context_window=3):
        """
        翻译SRT文件（带上下文的并发版本）
        :param srt_file: SRT文件路径
        :param target_lang: 目标语言
        :param keep_original: 是否保留原文（生成双语字幕）
        :param context_window: 上下文窗口大小（单侧），默认为3句
        :return: 翻译后的SRT文件路径
        """
        logging.info(f"开始翻译文件: {srt_file} 到 {target_lang}")
        try:
            # 读取SRT文件
            with open(srt_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 将SRT内容分成块
            blocks = content.strip().split('\n\n')
            translation_tasks = []
            
            # 创建线程池
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交翻译任务
                for i, block in enumerate(blocks):
                    lines = block.split('\n')
                    if len(lines) < 3:
                        continue
                    
                    index = lines[0]
                    timestamp = lines[1]
                    text = '\n'.join(lines[2:])

                    # 获取上下文
                    context_before = []
                    context_after = []
                    
                    # 获取前文
                    for j in range(max(0, i - context_window), i):
                        prev_block = blocks[j].split('\n')
                        if len(prev_block) >= 3:
                            context_before.append('\n'.join(prev_block[2:]))
                    
                    # 获取后文
                    for j in range(i + 1, min(len(blocks), i + context_window + 1)):
                        next_block = blocks[j].split('\n')
                        if len(next_block) >= 3:
                            context_after.append('\n'.join(next_block[2:]))

                    logging.info(f"提交翻译任务 {index}:")
                    logging.info(f"原文: {text}")

                    # 将任务提交到线程池
                    future = executor.submit(
                        self._translate_text_with_context, 
                        text, 
                        target_lang,
                        context_before,
                        context_after
                    )
                    translation_tasks.append((index, timestamp, text, future))

                # 收集翻译结果
                translated_blocks = []
                for index, timestamp, text, future in translation_tasks:
                    try:
                        translated_text = future.result()
                        # 应用词典替换
                        translated_text = self.apply_word_dict(translated_text)
                        
                        logging.info(f"翻译完成 {index}:")
                        logging.info(f"译文: {translated_text}\n")
                        
                        if keep_original:
                            translated_block = f"{index}\n{timestamp}\n{text}\n{translated_text}"
                        else:
                            translated_block = f"{index}\n{timestamp}\n{translated_text}"
                        translated_blocks.append(translated_block)
                    except Exception as e:
                        logging.error(f"翻译块 {index} 失败: {str(e)}")
                        raise

            # 保存翻译后的文件
            suffix = f'_{target_lang}_双语' if keep_original else f'_{target_lang}'
            output_file = srt_file.rsplit('.', 1)[0] + suffix + '.srt'
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(translated_blocks))

            return output_file

        except Exception as e:
            logging.error(f"翻译过程中出错: {str(e)}")
            raise

    def _translate_text_with_context(self, text, target_lang, context_before=None, context_after=None):
        """
        调用DeepSeek API翻译文本（带上下文）
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 构建带上下文的提示
        context_prompt = ""
        if context_before:
            context_prompt += f"前文：\n{'\n'.join(context_before)}\n\n"
        if context_after:
            context_prompt += f"后文：\n{'\n'.join(context_after)}\n\n"

        prompt = f"""请将以下文本翻译成{target_lang}，注意保持原文的语气和风格，并确保与上下文保持连贯：

{context_prompt}需要翻译的文本：
{text}

请只返回翻译结果，不要包含任何解释或额外的文本。"""

        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是一个专业的翻译助手，请直接提供翻译结果，不要添加任何解释或额外的文本。翻译时要考虑上下文，确保语义连贯。"},
                {"role": "user", "content": prompt}
            ]
        }

        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            result = response.json()
            translated = result['choices'][0]['message']['content'].strip()
            return translated

        except Exception as e:
            logging.error(f"API调用失败: {str(e)}")
            raise

def test():
    config_manager = ConfigManager()
    api_key = config_manager.get_api_key()
    api_base = config_manager.get_api_base()
    translator = Translator(api_key=api_key, api_base=api_base)
    translator.set_word_dict('word_dict.txt')
    result = translator._translate_text_with_context("你好，世界！yefeng", "English")
    translated_text = translator.apply_word_dict(result)
    print(translated_text)

# test()

def test_translate_srt():
    translator = Translator(api_key="your_openai_api_key", api_base="https://api.deepseek.com/v1")
    return translator.translate_srt("uploads/test.srt", "English", keep_original=True)

if __name__ == "__main__":
    test()