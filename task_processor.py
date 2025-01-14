import threading
import queue
import logging
import os
import genSrt

class TaskProcessor:
    def __init__(self):
        self.task_queue = queue.Queue()
        self.task_status = {}
        self._start_worker()

    def _start_worker(self):
        def worker():
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

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _process_task(self, task):
        task_id = task['task_id']
        video_path = task['video_path']
        output_dir = task['output_dir']
        filename = os.path.basename(video_path)

        try:
            # 提取音频（20-40%）
            self.task_status[task_id].update({
                'status': 'extracting_audio',
                'progress': 20,
                'message': '正在提取音频...'
            })

            audio_file = os.path.join(output_dir, genSrt.get_file_name(filename) + '.mp3')
            genSrt.extract_audio(video_path, audio_file)

            # 生成字幕（40-90%）
            self.task_status[task_id].update({
                'status': 'generating_subtitles',
                'progress': 40,
                'message': '正在生成字幕...'
            })

            genSrt.extract_subtitles(audio_file, output_dir)

            # 清理临时文件（90-95%）
            self.task_status[task_id].update({
                'status': 'cleaning',
                'progress': 90,
                'message': '正在清理临时文件...'
            })

            # 清理临时文件
            os.remove(audio_file)
            os.remove(video_path)

            # 更新完成状态
            srt_file = os.path.join(output_dir, genSrt.get_file_name(filename) + '.srt')
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

    def add_task(self, task_id, video_path, output_dir):
        self.task_status[task_id] = {
            'status': 'queued',
            'progress': 0,
            'message': '任务已加入队列...'
        }
        self.task_queue.put({
            'task_id': task_id,
            'video_path': video_path,
            'output_dir': output_dir
        })

    def get_status(self, task_id):
        return self.task_status.get(task_id) 