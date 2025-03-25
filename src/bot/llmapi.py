import json

import numpy as np
import requests
from openai import OpenAI

from .config import global_config
from ..event import MessageEvent
from .logger import register_logger

logger = register_logger("llm api",global_config.log_level)

class LLMAPI:
    """
    处理与llm交互
    """

    def __init__(self, llm_auth: dict,llm_models:dict):
        self.client = OpenAI(api_key=llm_auth["api_key"], base_url=llm_auth["base_url"])
        self.api_key = llm_auth["api_key"]
        self.base_url = llm_auth["base_url"]
        self.chat_model = llm_models["chat_model"]
        self.image_model = llm_models["image_model"]
        self.semantic_analysis_model = llm_models["semantic_analysis_model"]
        self.embedding_model = llm_models["embedding_model"]
        self.reranking_model = llm_models["reranking_model"]
        self.stream = llm_models
        ["stream"]

    def send_request_text(self, prompt: str) -> str:
        """
        发送文本请求
        """
        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "user", "content": prompt},
            ],
            stream=self.stream,
        )
        if self.stream:
            resp = ""
            for chunk in response:
                resp += chunk.choices[0].delta.content
            return resp
        else:
            return response.choices[0].message.content

    def send_request_image(self, prompt: str, image_base64: str) -> str:
        """
        发送图片请求
        图片格式为base64编码的jpeg
        """
        response = self.client.chat.completions.create(
            model=self.image_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            },
                        },
                    ],
                },
            ],
        )
        return response.choices[0].message.content

    def semantic_analysis(
        self, messageEvent: MessageEvent, chat_history: list[MessageEvent]
    ) -> dict:
        prompt = f"""<information>{global_config.bot_config['personality']}，你的网名是{global_config.bot_config['nickname']}<information>"""

        prompt += f"""<ChatHistory>你正在{"群聊" if messageEvent.is_group() else "私聊"}里聊天,最近的聊天上下文如下（最先发的在前）:"""
        for msg in chat_history:
            prompt += f"**昵称**为{msg.sender.nickname}的人说：{msg.get_plaintext()};"
        prompt += f"""</ChatHistory>"""
        prompt += f"<CurrentMessage>现在**昵称**为{messageEvent.sender.nickname}的人说：{messageEvent.get_plaintext()}</CurrentMessage>"
        prompt += f"<Requirement>现在请你根据<ChatHistory>和<CurrentMessage>标签标出的内容,分析出以下信息："

        prompt += f"""1. **ChatHistory** 的 **关键词** (两个词左右,一定要 **有标志性**,可以是动词,名词,人物等)"""
        prompt += f"""2. 听到这些对话后, **你** 的情感 (**一个准确的词语**)(注意,要表达的是 **你自己的情感**)"""
        prompt += f"""3. 根据 **ChatHistory** ,生成一段 **摘要** 概括你刚刚寻找到的 **关键词** (**一个简短的句子**,侧重于某个你认为最重要的关键词,不能笼统)"""

        prompt += f"""并打包为一个 json 发给我,json 格式如下:"""

        prompt += f"""{{"keywords": ["关键词1","关键词2"],"emotion": "情感","summary": "摘要"}}"""

        prompt += f"""注意，除了json字符串请不要输出多余内容</Requirement>"""

        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "user", "content": prompt},
            ]
        )
        resp = response.choices[0].message.content
        return json.loads(resp)

    def send_request_embedding(self, text: str):
        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=text,
            encoding_format="float",
        )
        return np.array(response.data[0].embedding, dtype=np.float32)

    def send_request_rerank(self, query_string: str, documents: list[str], reranking_k=None) -> list[dict]:
        reranking_k = global_config.memory_config['reranking_k'] if reranking_k is None else reranking_k
        url = self.base_url + "/rerank"
        payload = {
            "model": self.reranking_model,
            "query": query_string,
            "documents": documents,
            "top_n": reranking_k,
            "return_documents": False,
            "max_chunks_per_doc": 1024,
            "overlap_tokens": 80,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = requests.request("POST", url, json=payload, headers=headers)
        return response.json()['results']

    def create_image_description(self,base64_img:str)->str:
        response = self.client.chat.completions.create(
            model=self.image_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "请根据图像或表情包内容生成几句简短的描述，提到图像中人物的表情、动作、物品或其他明显特征,以及可能表达的情感。回答尽可能简短，**50字以内**,**不要**使用任何特殊符号",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_img}"
                            },
                        },
                    ],
                },
            ],
        )
        return response.choices[0].message.content

    def send_request_text_full(self, sys_prompt: str,user_prompt: str) -> dict:
        """
        发送文本请求

        :param sys_prompt: 系统提示
        :param user_prompt: 用户提示
        :return: json格式的响应
        """
        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        resp = response.choices[0].message.content
        return json.loads(resp)
