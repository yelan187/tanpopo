import sqlite3
import random
import base64
import asyncio
import subprocess
from PIL import Image
import hashlib

from .logger import register_logger

logger = register_logger("image manager")

class ImageDatabase:
    def __init__(self,db_path:str):
        self.db_path = db_path
        self.db = sqlite3.connect(db_path)

    def execute(self,query:str):
        cur = self.db.cursor()
        try:
            cur.execute(query)
        except Exception as error:
            logger.error(error)
        finally:
            cur.close()
            self.db.commit()
    
    def insert(self,hash:str,description:str,emotion:str):
        cur = self.db.cursor()
        query = '''insert into memes(hash,description,emotion) values(?,?,?)'''
        try:
            cur.execute(query,(hash,description,emotion))
        except Exception as error:
            logger.error(error)
        finally:
            cur.close()
            self.db.commit()

    def delete(self,id:int):
        cur = self.db.cursor()
        query = '''delete from memes where id = ?'''
        try:
            cur.execute(query,(id,))
        except Exception as error:
            logger.error(error)
        finally:
            cur.close()
            self.db.commit()

    def fetch_all(self):
        cur = self.db.cursor()
        query = '''select * from memes'''
        try:
            cur.execute(query)
            return cur.fetchall()
        except Exception as error:
            logger.error(error)
        finally:
            cur.close()
    
    def fetch_filename(self):
        cur = self.db.cursor()
        query = '''select hash from memes'''
        try:
            cur.execute(query)
            return cur.fetchall()
        except Exception as error:
            logger.error(error)
        finally:
            cur.close()


class MemeManager:
    def __init__(self):
        self.db = ImageDatabase('image.db')
        self.lock = asyncio.Lock()

    async def download_and_save_image(self,url:str)->str:
        """
        从 URL 下载图片，转换为指定格式并保存到指定路径。

        :param url: 图片的 URL 地址
        :param save_path: 保存图片的路径（包括文件名）
        :param target_format: 目标格式(默认为 PNG)可以是 'JPEG', 'PNG', 'BMP', 'GIF' 等
        """
        try:
            async with self.lock:
                subprocess.run(["wget", url, "-O", "img/temp_image"], check=True)
                img = Image.open("img/temp_image")
                img.convert("RGB")
                img.save("img/temp_image", "PNG")
                f = open('img/temp_image','rb')
                hash_md5 = hashlib.md5()
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
                filename = f"img/{hash_md5.hexdigest()}.png"
                img.save(filename, "PNG")
                f.close()
                logger.info(f"图片已保存为 {filename}")
                return filename
        except Exception as e:
            logger.error(f"处理图片时出错: {e}")
            return ""
    
    async def update_memes(self,urls):
        """
        保存消息中的所有表情包
        """
        raw = self.db.fetch_filename()
        if raw is None:
            before_files = []
        else:
            before_files = [x[0] for x in raw]
        for url in urls:
            filename = await self.download_and_save_image(url)
            filename = filename[4:]#remove prefix
            if not filename in before_files:
                logger.debug(f"新表情包: {filename}")
                self.db.insert(filename,"haha","sad")


    def get_meme(self)->str:
        files = self.db.fetch_filename()
        if files is None or len(files) == 0:
            return ""
        else:
            return self.encode_image("img/"+random.choice(files)[0])

    def encode_image(self,image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")