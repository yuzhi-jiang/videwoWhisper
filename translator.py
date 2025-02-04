import os
import logging
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from config_manager import ConfigManager
from ai_service import AIService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class Translator:
    def __init__(self):
        config = ConfigManager().get_config('translation')
        self.max_workers = config.get('max_workers', 5)
        self.context_window = config.get('context_window', 3)
        self.batch_size = config.get('batch_size', 10)
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
        """
        应用词典替换
        """
        for source, target in self.word_dict.items():
            text = text.replace(source, target)
        return text

    def translate_srt(self, srt_file: str, target_lang: str, keep_original: bool = False) -> str:
        """
        翻译SRT文件
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
            
            # 将blocks分成多个批次
            batches = []
            for i in range(0, len(blocks), self.batch_size):
                batch = blocks[i:i + self.batch_size]
                batch_info = self._prepare_batch(batch, i, blocks)
                if batch_info:
                    batches.append(batch_info)

            # 使用线程池并行处理批次
            translated_blocks = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有批次的处理任务
                future_to_batch = {
                    executor.submit(self._process_batch, batch, target_lang, keep_original): i 
                    for i, batch in enumerate(batches)
                }

                # 收集结果
                all_results = []
                for future in concurrent.futures.as_completed(future_to_batch):
                    batch_index = future_to_batch[future]
                    try:
                        result = future.result()
                        all_results.append((batch_index, result))
                    except Exception as e:
                        logging.error(f"处理批次 {batch_index} 时出错: {str(e)}")
                        raise

                # 按原始顺序排序结果
                all_results.sort(key=lambda x: x[0])
                for _, batch_blocks in all_results:
                    translated_blocks.extend(batch_blocks)

            # 保存翻译后的文件
            suffix = f'_{target_lang}_双语' if keep_original else f'_{target_lang}'
            output_file = srt_file.rsplit('.', 1)[0] + suffix + '.srt'
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(translated_blocks))

            logging.info(f"翻译完成，保存到: {output_file}")
            return output_file

        except Exception as e:
            logging.error(f"翻译过程中出错: {str(e)}")
            raise

    def _prepare_batch(self, batch: List[str], batch_start_index: int, all_blocks: List[str]) -> List[Dict]:
        """
        准备批次数据，包括上下文信息
        """
        batch_blocks = []
        for j, block in enumerate(batch):
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
            start_idx = max(0, batch_start_index + j - self.context_window)
            for k in range(start_idx, batch_start_index + j):
                prev_block = all_blocks[k].split('\n')
                if len(prev_block) >= 3:
                    context_before.append('\n'.join(prev_block[2:]))
            
            # 获取后文
            end_idx = min(len(all_blocks), batch_start_index + j + self.context_window + 1)
            for k in range(batch_start_index + j + 1, end_idx):
                next_block = all_blocks[k].split('\n')
                if len(next_block) >= 3:
                    context_after.append('\n'.join(next_block[2:]))
            
            batch_blocks.append({
                'index': index,
                'timestamp': timestamp,
                'text': text,
                'context_before': context_before,
                'context_after': context_after
            })
        
        return batch_blocks

    def _process_batch(self, batch_blocks: List[Dict], target_lang: str, keep_original: bool) -> List[str]:
        """
        处理单个批次
        """
        try:
            # 获取翻译文本
            texts = [block['text'] for block in batch_blocks]
            contexts_before = [block['context_before'] for block in batch_blocks]
            contexts_after = [block['context_after'] for block in batch_blocks]

            translated_texts = []
            for text, ctx_before, ctx_after in zip(texts, contexts_before, contexts_after):
                translated_text = self.ai_service.translate_text(text, target_lang, ctx_before, ctx_after)
                translated_text = self.apply_word_dict(translated_text)
                translated_texts.append(translated_text)
            
            # 重建字幕块
            translated_blocks = []
            for block_info, translated_text in zip(batch_blocks, translated_texts):
                if keep_original:
                    translated_block = (
                        f"{block_info['index']}\n"
                        f"{block_info['timestamp']}\n"
                        f"{block_info['text']}\n{translated_text}"
                    )
                else:
                    translated_block = (
                        f"{block_info['index']}\n"
                        f"{block_info['timestamp']}\n"
                        f"{translated_text}"
                    )
                translated_blocks.append(translated_block)
            
            return translated_blocks

        except Exception as e:
            logging.error(f"处理批次时出错: {str(e)}")
            raise

def test():
    translator = Translator()
    translator.set_word_dict('word_dict.txt')
    translated_file = translator.translate_srt("uploads/test.srt", "英语", keep_original=True)
    print(f"翻译后的文件: {translated_file}")

if __name__ == "__main__":
    test()