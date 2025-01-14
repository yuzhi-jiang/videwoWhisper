import os
import json
import requests
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class Translator:
    def __init__(self, api_key, api_base=None):
        self.api_key = api_key
        self.api_base = api_base or "https://api.deepseek.com/v1"
        self.max_workers = 5  # 设置最大并发数
        
    def translate_srt(self, srt_file, target_lang, keep_original=False):
        """
        翻译SRT文件（并发版本）
        :param srt_file: SRT文件路径
        :param target_lang: 目标语言
        :param keep_original: 是否保留原文（生成双语字幕）
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
                for block in blocks:
                    lines = block.split('\n')
                    if len(lines) < 3:
                        continue
                    
                    index = lines[0]
                    timestamp = lines[1]
                    text = '\n'.join(lines[2:])

                    logging.info(f"提交翻译任务 {index}:")
                    logging.info(f"原文: {text}")

                    # 将任务提交到线程池
                    future = executor.submit(self._translate_text, text, target_lang)
                    translation_tasks.append((index, timestamp, text, future))

                # 收集翻译结果
                translated_blocks = []
                for index, timestamp, text, future in translation_tasks:
                    try:
                        translated_text = future.result()
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

    def _translate_text(self, text, target_lang):
        """
        调用DeepSeek API翻译文本
        """
        # logging.info(f"调用API翻译文本: {text}")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        prompt = f"请将以下文本翻译成{target_lang}，保持原文的语气和风格：\n\n{text}"

        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system",
                 "content": "你是一个专业的翻译助手，请直接提供翻译结果，不要添加任何解释或额外的文本。"},
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
    translator = Translator(api_key="your_openai_api_key", api_base="https://api.deepseek.com/v1")
    result = translator._translate_text("你好，世界！", "English")
    print(result)

# test()

def test_translate_srt():
    translator = Translator(api_key="your_openai_api_key", api_base="https://api.deepseek.com/v1")
    return translator.translate_srt("uploads/test.srt", "English", keep_original=True)

