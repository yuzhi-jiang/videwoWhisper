import os
import logging
from config_manager import ConfigManager
from ai_service import AIService
from subtitle_processor import SubtitleProcessor

class SubtitleCorrector:
    def __init__(self):
        config = ConfigManager().get_config('subtitle_correction')
        self.processor = SubtitleProcessor(config)
        self.ai_service = AIService()
        print("初始化SubtitleCorrector")

    def correct_text(self, text: str, **kwargs) -> str:
        """纠正文本"""
        return self.ai_service.correct_subtitles(text, [], [])

    def correct_srt(self, srt_file: str) -> str:
        """
        纠正SRT文件中的识别错误
        :param srt_file: SRT文件路径
        :return: 纠正后的SRT文件路径
        """
        # 创建处理器列表，只包含纠错处理器
        processors = [(self.correct_text, {})]
        
        return self.processor.process_srt_pipeline(
            srt_file=srt_file,
            processors=processors,
            keep_original=False
        )

def test():
    # 添加logging基本配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    corrector = SubtitleCorrector()
    import time
    start_time = time.time()
    print("开始纠正字幕...")
    corrected_file = corrector.correct_srt("uploads/mp4_20250128_125857.srt")
    end_time = time.time()
    print(f"字幕纠错耗时: {end_time - start_time:.2f} 秒")
    print(f"纠正后的文件: {corrected_file}")

if __name__ == "__main__":
    test() 