import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.bot.image_manager import ImageDatabase

if __name__ == "__main__":
    db = ImageDatabase("image.db")
    query = """create table memes(id INTEGER PRIMARY KEY AUTOINCREMENT,\
                                                        hash VARCHAR(50),\
                                                        description VARCHAR(50),\
                                                        emotion VARCHAR(50)\
                                                        )"""
    db.execute(query)
