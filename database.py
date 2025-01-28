import sqlite3
import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, List, Tuple

class Database:
    def __init__(self, db_file='tasks.db'):
        self.db_file = db_file
        self.init_db()

    def init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            
            # 创建任务表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    original_filename TEXT NOT NULL,
                    stored_filename TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER DEFAULT 0,
                    message TEXT,
                    target_lang TEXT,
                    keep_original BOOLEAN,
                    model_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT,
                    process_time REAL
                )
            ''')
            
            # 创建文件表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS files (
                    file_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    stored_filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    is_temporary BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            ''')
            
            conn.commit()

    def generate_stored_filename(self, original_filename: str) -> str:
        """生成存储文件名，避免冲突"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name, ext = os.path.splitext(original_filename)
        return f"{name}_{timestamp}{ext}"

    def add_task(self, task_id: str, original_filename: str, stored_filename: str,
                file_type: str, target_lang: Optional[str] = None,
                keep_original: bool = False, model_name: str = 'large-v3') -> bool:
        """添加新任务"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO tasks (
                        task_id, original_filename, stored_filename, file_type,
                        status, target_lang, keep_original, model_name
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (task_id, original_filename, stored_filename, file_type,
                      'queued', target_lang, keep_original, model_name))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"添加任务失败: {str(e)}")
            return False

    def update_task_status(self, task_id: str, status: str, progress: int,
                          message: str, error_message: Optional[str] = None,
                          process_time: Optional[float] = None) -> bool:
        """更新任务状态"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                update_fields = {
                    'status': status,
                    'progress': progress,
                    'message': message,
                    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                if status == 'completed':
                    update_fields['completed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    update_fields['process_time'] = process_time
                
                if error_message:
                    update_fields['error_message'] = error_message

                set_clause = ', '.join([f"{k} = ?" for k in update_fields.keys()])
                values = list(update_fields.values())
                values.append(task_id)

                cursor.execute(f'''
                    UPDATE tasks
                    SET {set_clause}
                    WHERE task_id = ?
                ''', values)
                
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"更新任务状态失败: {str(e)}")
            return False

    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务信息"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logging.error(f"获取任务信息失败: {str(e)}")
            return None

    def get_all_tasks(self, limit: int = 100) -> List[Dict]:
        """获取所有任务信息"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM tasks 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"获取所有任务失败: {str(e)}")
            return []

    def add_file(self, file_id: str, task_id: str, file_type: str,
                original_filename: str, stored_filename: str,
                file_path: str, is_temporary: bool = False) -> bool:
        """添加文件记录"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO files (
                        file_id, task_id, file_type, original_filename,
                        stored_filename, file_path, is_temporary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (file_id, task_id, file_type, original_filename,
                      stored_filename, file_path, is_temporary))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"添加文件记录失败: {str(e)}")
            return False

    def get_task_files(self, task_id: str) -> List[Dict]:
        """获取任务相关的所有文件"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM files WHERE task_id = ?', (task_id,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"获取任务文件失败: {str(e)}")
            return []

    def cleanup_temporary_files(self, task_id: str) -> List[str]:
        """获取并删除任务的临时文件"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT file_path FROM files 
                    WHERE task_id = ? AND is_temporary = 1
                ''', (task_id,))
                temp_files = [row['file_path'] for row in cursor.fetchall()]
                
                # 删除文件记录
                cursor.execute('''
                    DELETE FROM files 
                    WHERE task_id = ? AND is_temporary = 1
                ''', (task_id,))
                conn.commit()
                
                return temp_files
        except Exception as e:
            logging.error(f"清理临时文件失败: {str(e)}")
            return []

    def get_incomplete_tasks(self) -> List[Dict]:
        """获取所有未完成的任务"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM tasks 
                    WHERE status NOT IN ('completed', 'error')
                    ORDER BY created_at ASC 
                ''')
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"获取未完成任务失败: {str(e)}")
            return [] 