import json
import os
import logging
from typing import Any, Dict, Optional

class ConfigManager:
    _instance = None
    _config = {}
    _config_file = 'config.json'

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self) -> None:
        """加载配置文件"""
        try:
            if os.path.exists(self._config_file):
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                logging.info(f"成功加载配置文件: {self._config_file}")
            else:
                logging.warning(f"配置文件不存在: {self._config_file}")
        except Exception as e:
            logging.error(f"加载配置文件失败: {str(e)}")
            self._config = {}

    def save_config(self) -> bool:
        """保存配置到文件"""
        try:
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
            logging.info(f"成功保存配置到文件: {self._config_file}")
            return True
        except Exception as e:
            logging.error(f"保存配置文件失败: {str(e)}")
            return False

    def get_config(self, section: Optional[str] = None) -> Dict:
        """
        获取配置
        :param section: 配置节名称，如果为None则返回整个配置
        :return: 配置字典
        """
        if section is None:
            return self._config
        return self._config.get(section, {})

    def set_config(self, section: str, key: str, value: Any) -> bool:
        """
        设置配置项
        :param section: 配置节名称
        :param key: 配置项键名
        :param value: 配置项值
        :return: 是否设置成功
        """
        try:
            if section not in self._config:
                self._config[section] = {}
            self._config[section][key] = value
            return True
        except Exception as e:
            logging.error(f"设置配置项失败: {str(e)}")
            return False

    def update_section(self, section: str, config: Dict) -> bool:
        """
        更新整个配置节
        :param section: 配置节名称
        :param config: 新的配置字典
        :return: 是否更新成功
        """
        try:
            self._config[section] = config
            return True
        except Exception as e:
            logging.error(f"更新配置节失败: {str(e)}")
            return False

    def get_api_key(self) -> Optional[str]:
        """获取API密钥"""
        return os.getenv('OPENAI_API_KEY') or self.get_config('api').get('openai_api_key')

    def get_api_base(self) -> Optional[str]:
        """获取API基础URL"""
        return os.getenv('OPENAI_API_BASE') or self.get_config('api').get('openai_api_base')

    def get_word_dict_config(self) -> Dict:
        """获取词典配置"""
        return self.get_config('word_dict')

    def get_translation_config(self) -> Dict:
        """获取翻译配置"""
        return self.get_config('translation')

# 使用示例
def test_config():
    # 获取配置管理器实例
    config_manager = ConfigManager()
    
    # 获取API配置
    api_key = config_manager.get_api_key()
    api_base = config_manager.get_api_base()
    print(f"API Key: {api_key}")
    print(f"API Base: {api_base}")
    
    # 更新配置
    config_manager.set_config('translation', 'max_workers', 10)
    config_manager.save_config()
    
    # 获取特定配置节
    translation_config = config_manager.get_translation_config()
    print(f"Translation Config: {translation_config}")

if __name__ == '__main__':
    test_config() 