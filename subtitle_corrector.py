import os
import logging
from typing import List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from config_manager import ConfigManager
from ai_service import AIService
import re

class SubtitleCorrector:
    def __init__(self):
        config = ConfigManager().get_config('subtitle_correction')
        self.context_window = config.get('context_window', 3)
        self.batch_size = config.get('batch_size', 10)
        self.max_workers = config.get('max_workers', 3)
        self.scene_gap = config.get('scene_gap', 2.0)  # 场景切换的时间间隔（秒）
        self.ai_service = AIService()
        print("初始化SubtitleCorrector")

    def _parse_timestamp(self, timestamp: str) -> Tuple[float, float]:
        """解析SRT时间戳，返回开始和结束时间（秒）"""
        start, end = timestamp.split(' --> ')
        
        def time_to_seconds(time_str):
            h, m, s = time_str.replace(',', '.').split(':')
            return float(h) * 3600 + float(m) * 60 + float(s)
        
        return time_to_seconds(start), time_to_seconds(end)

    def _detect_scenes(self, blocks: List[str]) -> List[List[Dict]]:
        """
        检测场景，将字幕分组
        返回场景列表，每个场景包含多个字幕块
        
        场景切分规则：
        1. 时间间隔超过阈值
        2. 当前场景字幕数量达到最大限制
        3. 检测到明显的语义分隔符
        """
        scenes = []
        current_scene = []
        last_end_time = 0
        max_scene_size = 15  # 每个场景最大字幕数量
        min_scene_size = 3   # 每个场景最小字幕数量

        def should_start_new_scene(block_data, current_scene_size):
            # 时间间隔条件
            time_gap = block_data['start_time'] - last_end_time > self.scene_gap
            # 场景大小条件
            size_limit = current_scene_size >= max_scene_size
            # 语义分隔条件（检查是否包含明显的语义分隔符）
            semantic_break = any(marker in block_data['text'] for marker in ['。。。', '...', '？', '！'])
            
            # 如果当前场景太小，即使满足其他条件也不切分
            if current_scene_size < min_scene_size:
                return False
                
            return (time_gap and semantic_break) or size_limit

        for block in blocks:
            lines = block.split('\n')
            if len(lines) < 3:
                continue

            index = lines[0]
            timestamp = lines[1]
            text = '\n'.join(lines[2:])
            
            start_time, end_time = self._parse_timestamp(timestamp)
            
            block_data = {
                'index': index,
                'timestamp': timestamp,
                'text': text,
                'start_time': start_time,
                'end_time': end_time
            }

            # 判断是否应该开始新场景
            if current_scene and should_start_new_scene(block_data, len(current_scene)):
                scenes.append(current_scene)
                logging.info(f"场景切换，当前场景大小: {len(current_scene)}")
                current_scene = []
            
            current_scene.append(block_data)
            last_end_time = end_time

        # 添加最后一个场景
        if current_scene:
            scenes.append(current_scene)

        # 输出场景统计信息
        scene_sizes = [len(scene) for scene in scenes]
        logging.info(f"场景数量: {len(scenes)}, 场景大小分布: 最小{min(scene_sizes)}, 最大{max(scene_sizes)}, 平均{sum(scene_sizes)/len(scenes):.1f}")

        return scenes

    def _merge_small_scenes(self, scenes: List[List[Dict]], min_subtitles: int = 5) -> List[List[Dict]]:
        """合并过小的场景"""
        merged_scenes = []
        current_scene = []
        
        for scene in scenes:
            current_scene.extend(scene)
            
            # 如果当前合并场景的字幕数量达到阈值，保存并开始新的场景
            if len(current_scene) >= min_subtitles:
                merged_scenes.append(current_scene)
                current_scene = []
        
        # 添加最后一个场景
        if current_scene:
            if merged_scenes:
                # 如果最后的场景太小，合并到前一个场景
                if len(current_scene) < min_subtitles:
                    merged_scenes[-1].extend(current_scene)
                else:
                    merged_scenes.append(current_scene)
            else:
                merged_scenes.append(current_scene)
        
        return merged_scenes

    def _process_scene(self, scene: List[Dict]) -> List[str]:
        """处理单个场景"""
        try:
            # 将场景中的所有字幕合并成一个文本块
            scene_text = '\n'.join(block['text'] for block in scene)
            # logging.info(f"场景文本: {scene_text}")
            # 纠正整个场景的文本
            corrected_text = self.ai_service.correct_subtitles(scene_text, [], [])
            
            # 将纠正后的文本重新分割成字幕块
            corrected_lines = corrected_text.strip().split('\n')
            
            # 确保纠正后的行数与原始字幕数量匹配
            if len(corrected_lines) != len(scene):
                # 如果行数不匹配，尝试智能分配
                corrected_blocks = self._smart_split_text(corrected_text, scene)
            else:
                # 如果行数匹配，直接组合
                corrected_blocks = [
                    f"{block['index']}\n{block['timestamp']}\n{text}"
                    for block, text in zip(scene, corrected_lines)
                ]
            
            return corrected_blocks

        except Exception as e:
            logging.error(f"处理场景时出错: {str(e)}")
            raise

    def _smart_split_text(self, text: str, original_blocks: List[Dict]) -> List[str]:
        """智能分割文本，尽量保持与原始字幕的对应关系"""
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text.strip())
        
        # 计算每个原始字幕块的平均字符数
        total_chars = len(text)
        total_blocks = len(original_blocks)
        avg_chars = total_chars / total_blocks
        
        # 根据原始字幕的时长比例分配文本
        result_blocks = []
        start_pos = 0
        
        for i, block in enumerate(original_blocks):
            if i == total_blocks - 1:
                # 最后一个块，使用剩余所有文本
                block_text = text[start_pos:]
            else:
                # 根据时长比例计算当前块应该包含的字符数
                duration = block['end_time'] - block['start_time']
                total_duration = original_blocks[-1]['end_time'] - original_blocks[0]['start_time']
                char_count = int(total_chars * (duration / total_duration))
                
                # 寻找最近的句子边界
                end_pos = start_pos + char_count
                if end_pos < len(text):
                    # 向后查找最近的句子结束符
                    next_period = text.find('。', end_pos)
                    next_question = text.find('？', end_pos)
                    next_exclamation = text.find('！', end_pos)
                    
                    # 找到最近的句子结束符
                    candidates = [pos for pos in [next_period, next_question, next_exclamation] if pos != -1]
                    if candidates:
                        end_pos = min(candidates) + 1
                
                block_text = text[start_pos:end_pos]
                start_pos = end_pos
            
            # 构建字幕块
            result_blocks.append(
                f"{block['index']}\n{block['timestamp']}\n{block_text.strip()}"
            )
        
        return result_blocks

    def correct_srt(self, srt_file: str) -> str:
        """
        纠正SRT文件中的识别错误（基于场景的批处理版本）
        :param srt_file: SRT文件路径
        :return: 纠正后的SRT文件路径
        """
        print("开始纠正字幕文件: ",srt_file)
        logging.info(f"开始纠正字幕文件: {srt_file}")
        try:
            # 读取SRT文件
            with open(srt_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 将SRT内容分成块
            blocks = content.strip().split('\n\n')
            
            # 检测场景
            scenes = self._detect_scenes(blocks)
            
            # 合并小场景
            merged_scenes = self._merge_small_scenes(scenes)
            
            logging.info(f"检测到 {len(merged_scenes)} 个场景")

            # 使用线程池并行处理场景
            corrected_blocks = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有场景的处理任务
                future_to_scene = {
                    executor.submit(self._process_scene, scene): i 
                    for i, scene in enumerate(merged_scenes)
                }

                # 收集结果
                all_results = []
                for future in concurrent.futures.as_completed(future_to_scene):
                    scene_index = future_to_scene[future] 
                    try:
                        result = future.result()
                        all_results.append((scene_index, result))
                        logging.info(f"场景 {scene_index + 1}/{len(merged_scenes)} 处理完成")
                    except Exception as e:
                        logging.error(f"处理场景 {scene_index} 时出错: {str(e)}")
                        raise
                # 按原始顺序排序结果
                logging.info("按原始顺序排序结果")
                all_results.sort(key=lambda x: x[0])
                for _, scene_blocks in all_results:
                    corrected_blocks.extend(scene_blocks)

            # 保存纠正后的文件
            output_file = srt_file.rsplit('.', 1)[0] + '_corrected.srt'
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(corrected_blocks))

            logging.info(f"字幕纠正完成，保存到: {output_file}")
            return output_file

        except Exception as e:
            logging.error(f"字幕纠正过程中出错: {str(e)}")
            raise

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