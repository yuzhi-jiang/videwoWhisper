import os
import logging
from typing import List, Dict
from config_manager import ConfigManager
from ai_service import AIService
from subtitle_processor import SubtitleProcessor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class Translator:
    def __init__(self):
        config = ConfigManager().get_config('translation')
        self.processor = SubtitleProcessor(config)
        self.ai_service = AIService()
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
        """应用词典替换"""
        for source, target in self.word_dict.items():
            text = text.replace(source, target)
        return text

    def translate_text(self, text: str, target_lang: str, **kwargs) -> str:
        """翻译文本"""
        translated = self.ai_service.translate_text(text, target_lang, [], [])
        return self.apply_word_dict(translated)

    def translate_srt(self, srt_file: str, target_lang: str, keep_original: bool = False) -> str:
        """
        翻译SRT文件
        :param srt_file: SRT文件路径
        :param target_lang: 目标语言
        :param keep_original: 是否保留原文（生成双语字幕）
        :return: 翻译后的SRT文件路径
        """
        # 创建处理器列表，只包含翻译处理器
        processors = [(self.translate_text, {'target_lang': target_lang})]
        
        return self.processor.process_srt_pipeline(
            srt_file=srt_file,
            processors=processors,
            keep_original=keep_original
        )

def test():
    translator = Translator()
    translator.set_word_dict('word_dict.txt')
    translated_file = translator.translate_srt("uploads/test.srt", "英语", keep_original=True)
    print(f"翻译后的文件: {translated_file}")

if __name__ == "__main__":
    test()