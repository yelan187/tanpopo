import base64
import json

import numpy as np
import requests
from openai import OpenAI

from .config import global_config
from ..event import MessageEvent


class LLMAPI:
    """
    处理与llm交互
    """

    def __init__(self, settings: dict):
        self.client = OpenAI(api_key=settings["api_key"], base_url=settings["base_url"])
        self.base_url = settings["base_url"]
        self.chat_model = settings["chat_model"]
        self.image_model = settings["image_model"]
        self.semantic_analysis_model = settings["semantic_analysis_model"]
        self.embedding_model = settings["embedding_model"]
        self.reranking_model = settings["reranking_model"]
        self.stream = settings["stream"]

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

        prompt += f"""1. **CurrentMessage** 的 **关键词** (**五个词左右**)"""
        prompt += f"""2. 听到这些对话后, **你** 的情感 (**一个准确的词语**)(注意,要表达的是 **你自己的情感**)"""
        prompt += f"""3. 根据关键词,主题,情感等,生成 **ChatHistory** 的 **摘要** (**一个简短的句子**)"""

        prompt += f"""并打包为一个 json 发给我,json 格式如下:"""

        prompt += f"""{{"keywords": ["关键词1","关键词2","关键词3","关键词4","关键词5"],"emotion": "情感","summary": "摘要"}}"""

        prompt += f"""</Requirement>"""

        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "user", "content": prompt},
            ],
            stream=self.stream,
            response_format={"type": "json_object"},
        )

        if self.stream:
            resp = ""
            for chunk in response:
                resp += chunk.choices[0].delta.content
        else:
            resp = response.choices[0].message.content
        return json.loads(resp)

    def send_request_embedding(self, text: str):
        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=text,
            encoding_format="float",
        )
        return np.array(response.data[0].embedding, dtype=np.float32)

    def send_request_rerank(self, query_string: str, documents: list[str]):
        url = self.base_url + "/rerank"
        payload = {
            "model": self.reranking_model,
            "query": query_string,
            "documents": documents,
            "top_n": global_config.memory_config['reranking_k'],
            "return_documents": False,
            "max_chunks_per_doc": 1024,
            "overlap_tokens": 80,
        }
        headers = {
            "Authorization": "Bearer sk-phlbcwawejllfeldnbgxonvrpokfwoeahkdtfzzbjgekrafv",
            "Content-Type": "application/json",
        }
        response = requests.request("POST", url, json=payload, headers=headers)
        return response.json()

    def create_image_description(self,base64_img:str)->str:
        response = self.client.chat.completions.create(
            model=self.image_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "请用简短的几句话描述这张图片的内容和可能表达的情感，**不要**超过50字, **不要**使用任何特殊符号,**不要**回答内容",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_img}"
                            },
                        },
                    ],
                },
            ],
        )
        return response.choices[0].message.content
