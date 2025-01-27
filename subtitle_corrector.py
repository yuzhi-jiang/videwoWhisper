import os
import logging
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from config_manager import ConfigManager
from ai_service import AIService

class SubtitleCorrector:
    def __init__(self):
        config = ConfigManager().get_config('subtitle_correction')
        self.context_window = config.get('context_window', 3)
        self.batch_size = config.get('batch_size', 10)
        self.max_workers = config.get('max_workers', 3)
        self.ai_service = AIService()

    def correct_srt(self, srt_file: str) -> str:
        """
        纠正SRT文件中的识别错误（多线程版本）
        :param srt_file: SRT文件路径
        :return: 纠正后的SRT文件路径
        """
        logging.info(f"开始纠正字幕文件: {srt_file}")
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
            
            print(f"总批次数: {len(batches)}")

            # 使用线程池并行处理批次
            corrected_blocks = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有批次的处理任务
                future_to_batch = {
                    executor.submit(self._process_batch, batch): i 
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
                    corrected_blocks.extend(batch_blocks)

            # 保存纠正后的文件
            output_file = srt_file.rsplit('.', 1)[0] + '_corrected.srt'
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(corrected_blocks))

            logging.info(f"字幕纠正完成，保存到: {output_file}")
            return output_file

        except Exception as e:
            logging.error(f"字幕纠正过程中出错: {str(e)}")
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

    def _process_batch(self, batch_blocks: List[Dict]) -> List[str]:
        """
        处理单个批次
        """
       
        # 打印当前批次中的所有字幕序号
        print("当前批次字幕序号:")
        print("size:",len(batch_blocks))
        for block in batch_blocks:
            print(f"字幕序号: {block['index']}")
        try:
            # 获取纠正后的文本
            texts = [block['text'] for block in batch_blocks]
            contexts_before = [block['context_before'] for block in batch_blocks]
            contexts_after = [block['context_after'] for block in batch_blocks]
            indexs = [block['index'] for block in batch_blocks]

            corrected_texts = []
            for text, ctx_before, ctx_after,index in zip(texts, contexts_before, contexts_after,indexs):
                corrected_text = self.ai_service.correct_subtitles(text, ctx_before, ctx_after)
                print(f"字幕序号: {index} 完成纠错")
                corrected_texts.append(corrected_text)
            
            # 重建字幕块
            corrected_blocks = []
            for block_info, corrected_text in zip(batch_blocks, corrected_texts):
                corrected_block = (
                    f"{block_info['index']}\n"
                    f"{block_info['timestamp']}\n"
                    f"{corrected_text}"
                )
                corrected_blocks.append(corrected_block)
            
            return corrected_blocks

        except Exception as e:
            logging.error(f"处理批次时出错: {str(e)}")
            raise

def test():
    corrector = SubtitleCorrector()
    import time
    start_time = time.time()
    corrected_file = corrector.correct_srt("uploads/test.srt")
    end_time = time.time()
    print(f"字幕纠错耗时: {end_time - start_time:.2f} 秒")
    print(f"纠正后的文件: {corrected_file}")

if __name__ == "__main__":
    test() 