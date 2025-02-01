import os
import logging
from typing import List, Dict, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
import re

class SubtitleProcessor:
    def __init__(self, config: dict):
        """
        初始化字幕处理器
        :param config: 配置字典，包含处理参数
        """
        self.max_workers = config.get('max_workers', 3)
        self.scene_gap = config.get('scene_gap', 2.0)  # 场景切换的时间间隔（秒）
        self.max_scene_size = config.get('max_scene_size', 15)  # 每个场景最大字幕数量
        self.min_scene_size = config.get('min_scene_size', 3)   # 每个场景最小字幕数量

    def _parse_timestamp(self, timestamp: str) -> Tuple[float, float]:
        """解析SRT时间戳，返回开始和结束时间（秒）"""
        try:
            parts = timestamp.split(' --> ')
            if len(parts) != 2:
                logging.error(f"无效的时间戳格式: {timestamp}")
                # 如果格式无效，返回一个默认值
                return 0.0, 0.0
            
            start, end = parts
            
            def time_to_seconds(time_str):
                try:
                    h, m, s = time_str.replace(',', '.').split(':')
                    return float(h) * 3600 + float(m) * 60 + float(s)
                except Exception as e:
                    logging.error(f"时间转换错误 '{time_str}': {str(e)}")
                    return 0.0
            
            return time_to_seconds(start), time_to_seconds(end)
            
        except Exception as e:
            logging.error(f"解析时间戳出错 '{timestamp}': {str(e)}")
            return 0.0, 0.0

    def _detect_scenes(self, blocks: List[str]) -> List[List[Dict]]:
        """
        检测场景，将字幕分组
        返回场景列表，每个场景包含多个字幕块
        """
        scenes = []
        current_scene = []
        last_end_time = 0

        def should_start_new_scene(block_data, current_scene_size):
            # 时间间隔条件
            time_gap = block_data['start_time'] - last_end_time > self.scene_gap
            # 场景大小条件
            size_limit = current_scene_size >= self.max_scene_size
            # 语义分隔条件（检查是否包含明显的语义分隔符）
            semantic_break = any(marker in block_data['text'] for marker in ['。。。', '...', '？', '！'])
            
            # 如果当前场景太小，即使满足其他条件也不切分
            if current_scene_size < self.min_scene_size:
                return False
                
            return (time_gap and semantic_break) or size_limit

        for i, block in enumerate(blocks):
            try:
                # 检查字幕块的基本格式
                lines = block.strip().split('\n')
                if len(lines) < 3:
                    logging.warning(f"跳过无效的字幕块 #{i + 1}: 行数不足")
                    continue

                # 验证字幕序号
                try:
                    int(lines[0])
                except ValueError:
                    logging.warning(f"跳过无效的字幕块 #{i + 1}: 无效的序号 '{lines[0]}'")
                    continue

                # 验证时间戳格式
                if ' --> ' not in lines[1]:
                    logging.warning(f"跳过无效的字幕块 #{i + 1}: 无效的时间戳格式 '{lines[1]}'")
                    continue

                index = lines[0]
                timestamp = lines[1]
                text = '\n'.join(lines[2:])
                
                start_time, end_time = self._parse_timestamp(timestamp)
                if start_time == 0.0 and end_time == 0.0:
                    logging.warning(f"跳过无效的字幕块 #{i + 1}: 时间戳解析失败")
                    continue
                
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

            except Exception as e:
                logging.error(f"处理字幕块 #{i + 1} 时出错: {str(e)}")
                continue

        # 添加最后一个场景
        if current_scene:
            scenes.append(current_scene)

        # 输出场景统计信息
        if scenes:
            scene_sizes = [len(scene) for scene in scenes]
            logging.info(f"场景数量: {len(scenes)}, 场景大小分布: 最小{min(scene_sizes)}, 最大{max(scene_sizes)}, 平均{sum(scene_sizes)/len(scenes):.1f}")
        else:
            logging.warning("没有检测到有效的场景")

        return scenes

    def _smart_split_text(self, text: str, original_blocks: List[Dict], keep_original: bool = False) -> List[str]:
        """智能分割文本，尽量保持与原始字幕的对应关系"""
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text.strip())
        
        # 计算每个原始字幕块的平均字符数
        total_chars = len(text)
        total_blocks = len(original_blocks)
        
        # 根据原始字幕的时长比例分配文本
        result_blocks = []
        start_pos = 0
        
        for i, block in enumerate(original_blocks):
            if i == total_blocks - 1:
                # 最后一个块，使用剩余所有文本
                processed_text = text[start_pos:]
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
                
                processed_text = text[start_pos:end_pos]
                start_pos = end_pos
            
            # 构建字幕块
            if keep_original:
                block_text = f"{block['text']}\n{processed_text.strip()}"
            else:
                block_text = processed_text.strip()
                
            result_blocks.append(
                f"{block['index']}\n{block['timestamp']}\n{block_text}"
            )
        
        return result_blocks

    def process_srt(self, srt_file: str, process_func: Callable, keep_original: bool = False, **kwargs) -> str:
        """
        处理SRT文件的通用方法
        :param srt_file: SRT文件路径
        :param process_func: 处理函数，接收文本和其他参数，返回处理后的文本
        :param keep_original: 是否保留原文
        :param kwargs: 传递给处理函数的其他参数
        :return: 处理后的SRT文件路径
        """
        try:
            # 读取SRT文件
            with open(srt_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 将SRT内容分成块
            blocks = content.strip().split('\n\n')
            
            # 检测场景
            scenes = self._detect_scenes(blocks)
            
            # 使用线程池并行处理场景
            processed_blocks = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有场景的处理任务
                def process_scene(scene):
                    try:
                        # 将场景中的所有字幕合并成一个文本块
                        scene_text = '\n'.join(block['text'] for block in scene)
                        # 处理文本
                        processed_text = process_func(scene_text, **kwargs)
                        # 分割处理后的文本
                        return self._smart_split_text(processed_text, scene, keep_original)
                    except Exception as e:
                        logging.error(f"处理场景时出错: {str(e)}")
                        raise

                # 提交任务并收集结果
                future_to_scene = {
                    executor.submit(process_scene, scene): i 
                    for i, scene in enumerate(scenes)
                }

                # 收集结果
                all_results = []
                processed_count = 0 # 已处理场景数量
                for future in concurrent.futures.as_completed(future_to_scene):
                    scene_index = future_to_scene[future]
                    try:
                        result = future.result()
                        all_results.append((scene_index, result))
                        processed_count += 1
                        logging.info(f"场景 {scene_index + 1}/{len(scenes)} 处理完成，已处理 {processed_count} 个场景")
                    except Exception as e:
                        logging.error(f"处理场景 {scene_index} 时出错: {str(e)}")
                        raise

                # 按原始顺序排序结果
                all_results.sort(key=lambda x: x[0])
                for _, scene_blocks in all_results:
                    processed_blocks.extend(scene_blocks)

            # 生成输出文件名
            output_file = self._generate_output_filename(srt_file, **kwargs)
            
            # 保存处理后的文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(processed_blocks))

            logging.info(f"处理完成，保存到: {output_file}")
            return output_file

        except Exception as e:
            logging.error(f"处理过程中出错: {str(e)}")
            raise

    def _generate_output_filename(self, input_file: str, **kwargs) -> str:
        """根据处理类型生成输出文件名"""
        base_name = input_file.rsplit('.', 1)[0]
        if 'target_lang' in kwargs:
            # 翻译任务
            suffix = f"_{kwargs['target_lang']}_双语" if kwargs.get('keep_original') else f"_{kwargs['target_lang']}"
        else:
            # 纠错任务
            suffix = '_corrected'
        return f"{base_name}{suffix}.srt"

    def process_srt_pipeline(self, srt_file: str, processors: List[Tuple[Callable, dict]], keep_original: bool = False) -> str:
        """
        处理SRT文件的流水线方法，支持多个处理器按顺序处理
        :param srt_file: SRT文件路径
        :param processors: 处理器列表，每个元素是(处理函数, 参数字典)的元组
        :param keep_original: 是否在最后保留原文（用于双语字幕）
        :return: 处理后的SRT文件路径
        """
        try:
            # 读取SRT文件
            with open(srt_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 将SRT内容分成块
            blocks = content.strip().split('\n\n')
            
            # 检测场景
            scenes = self._detect_scenes(blocks)
            if not scenes:
                return srt_file
                
            logging.info(f"检测到 {len(scenes)} 个场景")

            # 使用线程池并行处理场景
            processed_blocks = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有场景的处理任务
                def process_scene(scene):
                    try:
                        # 将场景中的所有字幕合并成一个文本块
                        scene_text = '\n'.join(block['text'] for block in scene)
                        
                        # 依次应用每个处理器
                        processed_text = scene_text
                        for proc_func, proc_args in processors:
                            processed_text = proc_func(processed_text, **proc_args)
                        
                        # 分割处理后的文本
                        return self._smart_split_text(processed_text, scene, keep_original)
                    except Exception as e:
                        logging.error(f"处理场景时出错: {str(e)}")
                        raise

                # 提交任务并收集结果
                future_to_scene = {
                    executor.submit(process_scene, scene): i 
                    for i, scene in enumerate(scenes)
                }

                # 收集结果
                all_results = []
                processed_count = 0 # 已处理场景数量
                for future in concurrent.futures.as_completed(future_to_scene):
                    scene_index = future_to_scene[future]
                    try:
                        result = future.result()
                        processed_count += 1
                        all_results.append((scene_index, result))
                        logging.info(f"场景 {scene_index + 1}/{len(scenes)} 处理完成 已处理 {processed_count} 个场景")
                    except Exception as e:
                        logging.error(f"处理场景 {scene_index} 时出错: {str(e)}")
                        raise

                # 按原始顺序排序结果
                all_results.sort(key=lambda x: x[0])
                for _, scene_blocks in all_results:
                    processed_blocks.extend(scene_blocks)

            # 生成输出文件名
            output_file = self._generate_pipeline_filename(srt_file, processors, keep_original)
            
            # 保存处理后的文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(processed_blocks))

            logging.info(f"处理完成，保存到: {output_file}")
            return output_file

        except Exception as e:
            logging.error(f"处理过程中出错: {str(e)}")
            raise

    def _generate_pipeline_filename(self, input_file: str, processors: List[Tuple[Callable, dict]], keep_original: bool) -> str:
        """根据处理流水线生成输出文件名"""
        base_name = input_file.rsplit('.', 1)[0]
        suffixes = []
        
        # 收集所有处理器的后缀
        for _, args in processors:
            if 'target_lang' in args:
                # 翻译处理
                suffix = f"_{args['target_lang']}"
                if keep_original:
                    suffix += '_双语'
                suffixes.append(suffix)
            else:
                # 纠错处理
                suffixes.append('_corrected')
        
        return f"{base_name}{''.join(suffixes)}.srt" 