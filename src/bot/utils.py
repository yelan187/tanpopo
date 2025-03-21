import subprocess
import asyncio
import hashlib

from PIL import Image

from .logger import register_logger
from ..event import MessageEvent

logger = register_logger("image utils")

lock = asyncio.Lock()

async def download_and_save_image(url:str)->str:
    """
    从 URL 下载图片，转换为指定格式并保存到指定路径。

    :param url: 图片的 URL 地址
    :param save_path: 保存图片的路径（包括文件名）
    :param target_format: 目标格式(默认为 PNG)可以是 'JPEG', 'PNG', 'BMP', 'GIF' 等
    """
    try:
        async with lock:
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
