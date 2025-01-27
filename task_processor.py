import threading
import queue
import logging
import os
import genSrt
from translator import Translator
from subtitle_corrector import SubtitleCorrector
from config_manager import ConfigManager
import concurrent.futures
import time

class TaskProcessor:
    def __init__(self, num_workers=2):
        self.task_queue = queue.Queue()
        self.task_status = {}
        self.num_workers = num_workers
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=num_workers)
        self.translator = Translator()
        self.corrector = SubtitleCorrector()
        self.active_tasks = 0  # 当前活动任务数
        self.max_active_tasks = 5  # 最大活动任务数
        self.task_lock = threading.Lock()  # 用于同步任务计数
        self._start_workers()

    def _start_workers(self):
        for _ in range(self.num_workers):
            self.executor.submit(self._worker_loop)

    def _worker_loop(self):
        while True:
            try:
                task = self.task_queue.get()
                if task is None:
                    break

                with self.task_lock:
                    self.active_tasks += 1
                    self.task_status[task['task_id']].update({
                        'status': 'processing',
                        'queue_position': None  # 移出队列
                    })

                self._process_task(task)

                with self.task_lock:
                    self.active_tasks -= 1
                    # 更新队列中任务的位置
                    self._update_queue_positions()

            except Exception as e:
                logging.error(f"处理任务时出错: {str(e)}")
                with self.task_lock:
                    self.active_tasks -= 1
            finally:
                self.task_queue.task_done()

    def _update_queue_positions(self):
        """更新队列中等待任务的位置"""
        queue_position = 1
        for task_id, status in self.task_status.items():
            if status['status'] == 'queued':
                status.update({'queue_position': queue_position})
                queue_position += 1

    def _process_task(self, task):
        task_id = task['task_id']
        file_path = task['file_path']
        output_dir = task['output_dir']
        file_type = task['file_type']
        target_lang = task.get('target_lang')
        keep_original = task.get('keep_original', False)
        model_name = task.get('model_name')
        filename = os.path.basename(file_path)
        start_time = time.time()

        try:
            if file_type == 'video':
                # 提取音频（10-20%）
                self.task_status[task_id].update({
                    'status': 'extracting_audio',
                    'progress': 10,
                    'message': '正在提取音频...'
                })

                audio_file = os.path.join(output_dir, genSrt.get_file_name(filename) + '.mp3')
                genSrt.extract_audio(file_path, audio_file)
                
                self.task_status[task_id].update({
                    'progress': 20,
                    'message': '音频提取完成...'
                })
            else:
                # 音频文件直接使用
                audio_file = file_path
                self.task_status[task_id].update({
                    'progress': 20,
                    'message': '开始处理音频...'
                })

            # 生成字幕（20-40%）
            self.task_status[task_id].update({
                'status': 'generating_subtitles',
                'progress': 30,
                'message': f'正在使用 {model_name} 模型生成字幕...'
            })

            genSrt.extract_subtitles(audio_file, output_dir, model_name=model_name)
            srt_file = os.path.join(output_dir, genSrt.get_file_name(filename) + '.srt')

            # 纠正字幕（40-60%）
            self.task_status[task_id].update({
                'status': 'correcting_subtitles',
                'progress': 40,
                'message': '正在纠正字幕...'
            })

            config = ConfigManager().get_config('subtitle_correction')
            if config.get('enabled', True):
                srt_file = self.corrector.correct_srt(srt_file)
                self.task_status[task_id].update({
                    'progress': 60,
                    'message': '字幕纠正完成...'
                })

            # 如果需要翻译（60-90%）
            if target_lang:
                self.task_status[task_id].update({
                    'status': 'translating',
                    'progress': 70,
                    'message': f'正在翻译为{target_lang}{"(双语)" if keep_original else ""}...'
                })
                
                translated_file = self.translator.translate_srt(srt_file, target_lang, keep_original)
                srt_file = translated_file  # 更新为翻译后的文件

            # 清理临时文件（90-95%）
            self.task_status[task_id].update({
                'status': 'cleaning',
                'progress': 90,
                'message': '正在清理临时文件...'
            })

            # 清理临时文件
            if file_type == 'video':
                os.remove(audio_file)
                os.remove(file_path)
            else:
                os.remove(file_path)  # 音频文件处理完后也删除

            # 计算处理时间
            process_time = round(time.time() - start_time, 1)

            # 更新完成状态
            self.task_status[task_id].update({
                'status': 'completed',
                'progress': 100,
                'message': f'处理完成！总耗时: {process_time}秒',
                'srt_file': srt_file,
                'process_time': process_time
            })

        except Exception as e:
            # 即使出错也记录处理时间
            process_time = round(time.time() - start_time, 1)
            self.task_status[task_id].update({
                'status': 'error',
                'message': f'处理失败: {str(e)}',
                'process_time': process_time
            })
            logging.error(f"处理任务 {task_id} 时出错: {str(e)}")

    def add_task(self, task_id, file_path, output_dir, file_type='video', target_lang=None, keep_original=False, model_name='large-v3'):
        """
        添加任务到队列
        :return: (bool, str) - (是否成功添加, 消息)
        """
        with self.task_lock:
            # 计算当前总任务数（活动 + 队列中）
            total_tasks = self.active_tasks + sum(1 for status in self.task_status.values() 
                                                if status['status'] == 'queued')
            
            if total_tasks >= self.max_active_tasks:
                return False, f"任务队列已满（最大{self.max_active_tasks}个任务），请等待其他任务完成后再试"

            queue_position = total_tasks + 1
            self.task_status[task_id] = {
                'status': 'queued',
                'progress': 0,
                'message': '任务已加入队列...',
                'start_time': time.time(),
                'queue_position': queue_position
            }

        self.task_queue.put({
            'task_id': task_id,
            'file_path': file_path,
            'output_dir': output_dir,
            'file_type': file_type,
            'target_lang': target_lang,
            'keep_original': keep_original,
            'model_name': model_name
        })

        return True, f"任务已添加到队列，位置：{queue_position}"

    def get_status(self, task_id):
        return self.task_status.get(task_id)

    def get_all_status(self):
        """获取所有任务的状态"""
        return self.task_status

    def get_queue_info(self):
        """获取队列信息"""
        return {
            'active_tasks': self.active_tasks,
            'max_tasks': self.max_active_tasks,
            'queued_tasks': sum(1 for status in self.task_status.values() 
                              if status['status'] == 'queued')
        } 