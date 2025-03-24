import random
import base64
import asyncio
import subprocess
import hashlib
from datetime import datetime

from PIL import Image
import faiss
import numpy as np

from .database import Database
from .llmapi import LLMAPI
from .logger import register_logger
from .config import global_config

logger = register_logger("image manager",global_config.log_level)

class ImageManager:
    def __init__(self):
        self.db = Database(global_config.database_config['database_name'],global_config.database_config['uri'])
        self.llm_api = LLMAPI(global_config.llm_auth,global_config.llm_models)
        self.index = faiss.IndexFlatL2(1024)
        self.table_name = global_config.memes_config['memes_table_name']
        self.data_length = 0
        self.lock = asyncio.Lock()

    async def load_memes(self):
        """
        从数据库中加载所有图片数据
        """
        if self.data_length > 0:
            return
        logger.info("正在加载表情包数据")
        data = self.db.find(self.table_name,{},{"embedding":1})
        embeddings = []
        for l in data:
            embeddings.append(np.array(l['embedding']))
        if len(embeddings) == 0:
            logger.warning("表情包数据为空")
            return
        self.index.add(np.array(embeddings))
        self.data_length = len(embeddings)
        logger.info(f"表情包数据加载完成，共 {self.data_length} 个")

    async def update_img_from_url(self,url:str,is_meme:bool)->str:
        """
        从 URL 下载图片并决定是否保存

        :param url: 图片的 URL 地址
        :param save_path: 保存图片的路径（包括文件名）
        :param target_format: 目标格式(默认为 PNG)可以是 'JPEG', 'PNG', 'BMP', 'GIF' 等

        :return description: 图片的描述
        """
        try:
            async with self.lock:
                subprocess.run(["wget", url, "-O", "tmp/temp_image"], check=True)
                img = Image.open("tmp/temp_image")
                img.convert("RGB")
                img.save("tmp/temp_image", "PNG")
                f = open('tmp/temp_image','rb')
                hash_md5 = hashlib.md5()
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
                hash = hash_md5.hexdigest()
                data = self.db.find_one(self.table_name,{"hash":hash})
                img_base64 = await self.encode_image('tmp/temp_image') 
                description = self.llm_api.create_image_description(img_base64)
                if data is None and is_meme and self.decide_if_add():
                    embedding = self.llm_api.send_request_embedding(description)
                    new_time = int(datetime.now(global_config.time_zone).timestamp())
                    new_record = {
                        "_id":self.data_length,
                        "hash":hash,
                        "base64":img_base64,
                        "description":description,
                        "embedding":embedding.tolist(),
                        "create_time":new_time,
                        "update_time":new_time,
                        "hits":0
                    }
                    self.db.insert(self.table_name,new_record)
                    self.index.add(np.array([embedding]))
                    self.data_length += 1
                    logger.info(f"成功添加表情,描述为 {description}")
                return description
        except Exception as e:
            logger.error(f"处理图片时出错: {e}")
            return ""

    async def match_meme(self,message:str):
        """
        根据消息匹配表情包
        
        :param message: 消息内容
        :return: 表情包base64
        """
        if message == "":
            return {}
        query_embedding = self.llm_api.send_request_embedding(message)
        logger.info(f"查询与[{message}]相关的表情包")
        distances, indices = self.index.search(query_embedding.reshape(1, -1), 1)
        if indices[0][0] == -1:
            logger.info("表情包数据库为空")
            return ""
        data = self.db.find_one(self.table_name,{"_id":indices[0][0].item()})
        if data is None:
            logger.info("未找到相关的表情包")
            return ""
        else:
            logger.info(f"找到相关的表情包,描述为 {data['description']}")
            return data["base64"]

    def decide_if_add(self):
        return random.random() < global_config.memes_config['add_meme_probability']

    async def create_img_description_update(self,urls:list[str],is_meme:list[bool]):
        """
        根据url更新表情包库并返回所有表情包/图片的描述
        """
        descriptions = []
        for i in range(len(urls)):
            description = await self.update_img_from_url(urls[i],is_meme[i])
            descriptions.append(description)
        return descriptions

    async def encode_image(self,image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")