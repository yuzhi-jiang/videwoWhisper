import threading
import queue
import logging
import os
import genSrt
from translator import Translator
from subtitle_corrector import SubtitleCorrector
from subtitle_processor import SubtitleProcessor
from config_manager import ConfigManager
import concurrent.futures
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Tuple, Optional, List
from datetime import datetime
from database import Database

class TaskProcessor:
    def __init__(self, num_workers=2):
        self.num_workers = num_workers
        self.max_active_tasks = num_workers * 3  # 最大任务数为工作线程数的3倍
        self.task_queue = queue.Queue()
        self.active_tasks = 0
        self.task_lock = threading.Lock()
        
        # 初始化数据库
        self.db = Database()
        
        # 初始化其他组件
        config = ConfigManager().get_config('subtitle_correction')
        self.processor = SubtitleProcessor(config)  # 添加处理器实例
        self.corrector = SubtitleCorrector()
        self.translator = Translator()
        
        # 启动工作线程
        self.workers = []
        for _ in range(num_workers):
            worker = threading.Thread(target=self._worker, daemon=True)
            worker.start()
            self.workers.append(worker)
            
        # 恢复未完成的任务
        self._recover_incomplete_tasks()

    def _recover_incomplete_tasks(self):
        """恢复未完成的任务"""
        incomplete_tasks = self.db.get_incomplete_tasks()
        for task in incomplete_tasks:
            # 检查文件是否仍然存在
            files = self.db.get_task_files(task['task_id'])
            if not files or not os.path.exists(files[0]['file_path']):
                # 如果文件不存在，将任务标记为错误
                self.db.update_task_status(
                    task['task_id'],
                    'error',
                    0,
                    '系统重启后文件已丢失',
                    error_message='文件不存在'
                )
                continue
            
            # 将任务重新加入队列
            self.task_queue.put({
                'task_id': task['task_id'],
                'file_path': files[0]['file_path'],
                'output_dir': os.path.dirname(files[0]['file_path']),
                'file_type': task['file_type'],
                'target_lang': task['target_lang'],
                'keep_original': task['keep_original'],
                'model_name': task['model_name']
            })
            
            # 更新任务状态
            self.db.update_task_status(
                task['task_id'],
                'queued',
                0,
                '任务已重新加入队列'
            )

    def _worker(self):
        """工作线程函数"""
        while True:
            task = self.task_queue.get()
            if task is None:
                break
                
            with self.task_lock:
                self.active_tasks += 1
                
            try:
                self._process_task(task)
            except Exception as e:
                logging.error(f"处理任务 {task['task_id']} 时出错: {str(e)}")
                self.db.update_task_status(
                    task['task_id'],
                    'error',
                    0,
                    f'处理失败: {str(e)}',
                    error_message=str(e)
                )
            finally:
                with self.task_lock:
                    self.active_tasks -= 1
                self.task_queue.task_done()

    def _process_task(self, task):
        task_id = task['task_id']
        file_path = task['file_path']
        output_dir = task['output_dir']
        file_type = task['file_type']
        target_lang = task.get('target_lang')
        keep_original = task.get('keep_original', False)
        model_name = task.get('model_name')
        start_time = time.time()

        try:
            if file_type == 'video':
                # 提取音频（10-20%）
                self.db.update_task_status(task_id, 'extracting_audio', 10, '正在提取音频...')

                # 生成临时音频文件名
                audio_filename = f"temp_audio_{task_id}.mp3"
                audio_file = os.path.join(output_dir, audio_filename)
                if not os.path.exists(audio_file):
                    genSrt.extract_audio(file_path, audio_file)
                
                    # 记录临时音频文件
                    self.db.add_file(
                        file_id=str(uuid.uuid4()),
                        task_id=task_id,
                        file_type='audio',
                        original_filename=audio_filename,
                        stored_filename=audio_filename,
                        file_path=audio_file,
                        is_temporary=True
                    )
                
                self.db.update_task_status(task_id, 'extracting_audio', 20, '音频提取完成...')
            else:
                # 音频文件直接使用
                audio_file = file_path
                self.db.update_task_status(task_id, 'processing', 20, '开始处理音频...')

            # 生成字幕（20-40%）
            self.db.update_task_status(
                task_id,
                'generating_subtitles',
                30,
                f'正在使用 {model_name} 模型生成字幕...'
            )

            # 生成字幕文件名
            task_info = self.db.get_task(task_id)
            srt_filename = f"{os.path.splitext(task_info['original_filename'])[0]}.srt"
            stored_srt_filename = self.db.generate_stored_filename(srt_filename)
            srt_file = os.path.join(output_dir, stored_srt_filename)

            # 使用统一的文件名生成字幕
            genSrt.extract_subtitles(
                audio_file, 
                output_dir, 
                model_name=model_name,
                output_filename=stored_srt_filename
            )
            
            # 记录字幕文件
            self.db.add_file(
                file_id=str(uuid.uuid4()),
                task_id=task_id,
                file_type='subtitle',
                original_filename=srt_filename,
                stored_filename=stored_srt_filename,
                file_path=srt_file,
                is_temporary=False
            )

            # 构建处理器列表
            processors = []
            config = ConfigManager().get_config('subtitle_correction')
            
            # 如果启用了纠错，添加纠错处理器
            if config.get('enabled', True):
                self.db.update_task_status(task_id, 'correcting_subtitles', 40, '正在纠正字幕...')
                processors.append((self.corrector.correct_text, {}))
            
            # 如果需要翻译，添加翻译处理器
            if target_lang:
                self.db.update_task_status(
                    task_id,
                    'translating',
                    70,
                    f'正在翻译为{target_lang}{"(双语)" if keep_original else ""}...'
                )
                processors.append((self.translator.translate_text, {'target_lang': target_lang}))
            
            # 如果有处理器，执行处理流水线
            if processors:
                processed_file = self.processor.process_srt_pipeline(
                    srt_file=srt_file,
                    processors=processors,
                    keep_original=keep_original
                )
                
                if processed_file != srt_file:
                    # 记录处理后的文件
                    self.db.add_file(
                        file_id=str(uuid.uuid4()),
                        task_id=task_id,
                        file_type='subtitle_processed',
                        original_filename=srt_filename,
                        stored_filename=os.path.basename(processed_file),
                        file_path=processed_file,
                        is_temporary=False
                    )
                    srt_file = processed_file

            # 清理临时文件（90-95%）
            self.db.update_task_status(task_id, 'cleaning', 90, '正在清理临时文件...')
            
            # 获取并删除临时文件
            temp_files = self.db.cleanup_temporary_files(task_id)
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception as e:
                    logging.error(f"删除临时文件 {temp_file} 失败: {str(e)}")

            # 计算处理时间
            process_time = round(time.time() - start_time, 1)

            # 更新完成状态
            self.db.update_task_status(
                task_id,
                'completed',
                100,
                f'处理完成！总耗时: {process_time}秒',
                process_time=process_time
            )

        except Exception as e:
            # 即使出错也记录处理时间
            process_time = round(time.time() - start_time, 1)
            self.db.update_task_status(
                task_id,
                'error',
                0,
                f'处理失败: {str(e)}',
                error_message=str(e),
                process_time=process_time
            )
            logging.error(f"处理任务 {task_id} 时出错: {str(e)}")
            raise

    def add_task(self, task_id: str, file_path: str, output_dir: str,
                file_type: str = 'video', target_lang: Optional[str] = None,
                keep_original: bool = False, model_name: str = 'large-v3') -> Tuple[bool, str]:
        """
        添加任务到队列
        :return: (bool, str) - (是否成功添加, 消息)
        """
        with self.task_lock:
            # 计算当前总任务数（活动 + 队列中）
            total_tasks = self.active_tasks + self.task_queue.qsize()
            
            if total_tasks >= self.max_active_tasks:
                return False, f"任务队列已满（最大{self.max_active_tasks}个任务），请等待其他任务完成后再试"

            # 生成存储文件名
            original_filename = os.path.basename(file_path)
            stored_filename = self.db.generate_stored_filename(original_filename)
            new_file_path = os.path.join(output_dir, stored_filename)
            
            # 移动文件到新位置
            os.rename(file_path, new_file_path)
            
            # 添加任务到数据库
            self.db.add_task(
                task_id=task_id,
                original_filename=original_filename,
                stored_filename=stored_filename,
                file_type=file_type,
                target_lang=target_lang,
                keep_original=keep_original,
                model_name=model_name
            )
            
            # 记录原始文件
            self.db.add_file(
                file_id=str(uuid.uuid4()),
                task_id=task_id,
                file_type=file_type,
                original_filename=original_filename,
                stored_filename=stored_filename,
                file_path=new_file_path,
                is_temporary=False
            )

            # 添加任务到处理队列
            self.task_queue.put({
                'task_id': task_id,
                'file_path': new_file_path,
                'output_dir': output_dir,
                'file_type': file_type,
                'target_lang': target_lang,
                'keep_original': keep_original,
                'model_name': model_name
            })

            queue_position = total_tasks + 1
            return True, f"任务已添加到队列，位置：{queue_position}"

    def get_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        return self.db.get_task(task_id)

    def get_all_status(self) -> List[Dict]:
        """获取所有任务状态"""
        return self.db.get_all_tasks()

    def get_queue_info(self) -> Dict:
        """获取队列信息"""
        return {
            'active_tasks': self.active_tasks,
            'queued_tasks': self.task_queue.qsize(),
            'max_tasks': self.max_active_tasks
        } 