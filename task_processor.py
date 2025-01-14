import threading
import queue
import logging
import os
import genSrt
from translator import Translator
import concurrent.futures

class TaskProcessor:
    def __init__(self, openai_api_key, openai_api_base=None, num_workers=2):
        self.task_queue = queue.Queue()
        self.task_status = {}
        self.num_workers = num_workers
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=num_workers)
        self.translator = Translator(openai_api_key, openai_api_base)
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
                self._process_task(task)
            except Exception as e:
                logging.error(f"处理任务时出错: {str(e)}")
            finally:
                self.task_queue.task_done()

    def _process_task(self, task):
        task_id = task['task_id']
        file_path = task['file_path']
        output_dir = task['output_dir']
        file_type = task['file_type']
        target_lang = task.get('target_lang')
        keep_original = task.get('keep_original', False)
        filename = os.path.basename(file_path)

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

            # 生成字幕（20-70%）
            self.task_status[task_id].update({
                'status': 'generating_subtitles',
                'progress': 30,
                'message': '正在生成字幕...'
            })

            genSrt.extract_subtitles(audio_file, output_dir)
            srt_file = os.path.join(output_dir, genSrt.get_file_name(filename) + '.srt')

            # 如果需要翻译（70-90%）
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
            elif not task.get('keep_audio', False):  # 如果是音频文件且不保留，则删除
                os.remove(file_path)

            # 更新完成状态
            self.task_status[task_id].update({
                'status': 'completed',
                'progress': 100,
                'message': '处理完成！',
                'srt_file': srt_file
            })

        except Exception as e:
            self.task_status[task_id].update({
                'status': 'error',
                'message': f'处理失败: {str(e)}'
            })
            logging.error(f"处理任务 {task_id} 时出错: {str(e)}")

    def add_task(self, task_id, file_path, output_dir, file_type='video', keep_audio=False, target_lang=None, keep_original=False):
        """
        添加任务到队列
        :param task_id: 任务ID
        :param file_path: 文件路径
        :param output_dir: 输出目录
        :param file_type: 文件类型 ('video' 或 'audio')
        :param keep_audio: 是否保留音频文件
        :param target_lang: 目标翻译语言（可选）
        :param keep_original: 是否保留原文（生成双语字幕）
        """
        self.task_status[task_id] = {
            'status': 'queued',
            'progress': 0,
            'message': '任务已加入队列...'
        }
        self.task_queue.put({
            'task_id': task_id,
            'file_path': file_path,
            'output_dir': output_dir,
            'file_type': file_type,
            'keep_audio': keep_audio,
            'target_lang': target_lang,
            'keep_original': keep_original
        })

    def get_status(self, task_id):
        return self.task_status.get(task_id)

    def get_all_status(self):
        """获取所有任务的状态"""
        return self.task_status 