import json
import logging
from typing import List, Optional
from openai import OpenAI
from config_manager import ConfigManager

class AIService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AIService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """初始化AI服务"""
        config = ConfigManager()
        self.client = OpenAI(
            api_key=config.get_api_key(),
            base_url=config.get_api_base()
        )
        self.model = config.get_translation_config().get('default_model')
        print("初始化AI服务")

    def correct_subtitles(self, text: str, context_before: Optional[List[str]] = None, context_after: Optional[List[str]] = None) -> str:
        """
        纠正字幕文本
        :param text: 需要纠正的文本
        :param context_before: 前文上下文
        :param context_after: 后文上下文
        :return: 纠正后的文本
        """
        errResponse = None
        try:
            # 构建上下文提示
            context_prompt = ""
            if context_before:
                context_prompt += f"前文：\n{'\n'.join(context_before)}\n\n"
            if context_after:
                context_prompt += f"后文：\n{'\n'.join(context_after)}\n\n"

            prompt = f"""请纠正以下语音识别文本中的错误，保持原意的同时确保语言通顺、符合语境：

            {context_prompt}需要纠正的文本：
            {text}

            请只返回纠正后的文本，不要包含任何解释或额外的文本。如果文本已经正确，直接返回原文。"""
            
            response = self.sendChat(prompt,3)
            errResponse=response
            if response.choices[0].message.content.strip() != text:
                print(f"需要纠正的文本: {text}")
                print(f"纠正后的文本: {response.choices[0].message.content.strip()}")
                
            return response.choices[0].message.content.strip()
        except json.JSONDecodeError as e:
            logging.info(f"原文本: {text}")
            logging.info(f"response: {errResponse}")
            logging.error(f"JSON解析错误: {e}")
            # 发生错误时返回原文本
            return text
        except Exception as e:
            logging.error(f"字幕纠错失败: {str(e)}")
            raise

    def sendChat(self, prompt,retry_count=0):
        response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一个专业的语音识别后处理助手。你的任务是纠正语音识别的错误，确保文本通顺、准确，并与上下文保持一致。只返回纠正后的文本，不要添加任何解释。"
                        },
                        {"role": "user", "content": prompt}
                    ],
                    stream=False
                )
        if response==None and retry_count>0:
            return self.sendChat(prompt,retry_count-1)
        return response

    def translate_text(self, text: str, target_lang: str, context_before: Optional[List[str]] = None, context_after: Optional[List[str]] = None) -> str:
        """
        翻译文本
        :param text: 需要翻译的文本
        :param target_lang: 目标语言
        :param context_before: 前文上下文
        :param context_after: 后文上下文
        :return: 翻译后的文本
        """
        errResponse = None
        try:
            # 构建上下文提示
            context_prompt = ""
            if context_before:
                context_prompt += f"前文：\n{'\n'.join(context_before)}\n\n"
            if context_after:
                context_prompt += f"后文：\n{'\n'.join(context_after)}\n\n"

            prompt = f"""你是一位专业的视频字幕翻译专家。请将以下文本翻译成{target_lang}。

翻译要求：
1. 严格保持原文的断句结构，如果原文分成两行，翻译后也必须保持两行
2. 每行翻译的长度要适合字幕显示（不要太长）
3. 保持原文的表达方式和语气
4. 确保与上下文的连贯性
5. 对于口语化的表达，翻译时要使用对应语言中自然的口语表达
6. 保持专业术语的准确性
7. 如果原文有重复或口吃，翻译时要适当保留这种特点

注意：请严格按照原文的行数进行翻译，保持相同的断句结构，这对于字幕时间轴的对应至关重要。

{context_prompt}需要翻译的文本：
{text}

请只返回翻译结果，不要包含任何解释或额外的文本。每行翻译请单独成行，与原文结构保持一致。"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的字幕翻译助手，必须严格保持原文的断句结构，确保翻译后的行数与原文完全一致。请直接提供翻译结果，不要添加任何解释或额外的文本。"
                    },
                    {"role": "user", "content": prompt}
                ],
                stream=False
            )
            errResponse=response
            return response.choices[0].message.content.strip()
        except json.JSONDecodeError as e:
            logging.info(f"原文本: {text}")
            logging.info(f"response: {errResponse}")
            logging.error(f"JSON解析错误: {e}")
            # 发生错误时返回原文本
            return text
        except Exception as e:
            logging.error(f"文本翻译失败: {str(e)}")
            raise

    def batch_process(self, texts: List[str], process_type: str, **kwargs) -> List[str]:
        """
        批量处理文本（纠错或翻译）
        :param texts: 文本列表
        :param process_type: 处理类型 ('correct' 或 'translate')
        :param kwargs: 其他参数（如 target_lang）
        :return: 处理后的文本列表
        """
        results = []
        for text in texts:
            try:
                if process_type == 'correct':
                    result = self.correct_subtitles(
                        text,
                        kwargs.get('context_before', []),
                        kwargs.get('context_after', [])
                    )
                elif process_type == 'translate':
                    result = self.translate_text(
                        text,
                        kwargs['target_lang'],
                        kwargs.get('context_before', []),
                        kwargs.get('context_after', [])
                    )
                else:
                    raise ValueError(f"不支持的处理类型: {process_type}")
                
                results.append(result)
            except Exception as e:
                logging.error(f"处理文本失败: {str(e)}")
                raise

        return results

def test():
    # 测试AI服务
    service = AIService()
    
    # 测试字幕纠错
    corrected = service.correct_subtitles(
        "这是一个测试文本，包含一些误错的词语和表达",
        ["前文上下文1", "前文上下文2"],
        ["后文上下文1", "后文上下文2"]
    )
    print(f"纠错结果: {corrected}")
    
    # 测试翻译
    translated = service.translate_text(
        "这是一个测试文本",
        "英语",
        ["前文上下文1"],
        ["后文上下文1"]
    )
    print(f"翻译结果: {translated}")

if __name__ == "__main__":
    test() 