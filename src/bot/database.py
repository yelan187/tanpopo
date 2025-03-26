from pymongo import MongoClient, ReturnDocument
from pymongo.errors import ServerSelectionTimeoutError, PyMongoError
from .logger import register_logger
from .config import global_config

class Database:
    def __init__(self, db_name: str, uri: str = "mongodb://localhost:27017/"):
        """
        初始化数据库连接
        """
        try:
            self.client = MongoClient(uri)
            self.db = self.client[db_name]
            self.logger = register_logger('database',global_config.log_level)
            self.logger.debug(f"尝试连接数据库: {db_name}")
        except ServerSelectionTimeoutError as e:
            self.logger.error(f"无法连接到MongoDB: {e}")
            raise
        except PyMongoError as e:
            self.logger.error(f"MongoDB操作异常: {e}")
            raise

    def insert(self, collection_name: str, data: dict):
        """
        插入一条数据

        :param collection_name: 集合名称
        :param data: 插入的文档数据
        :return: 插入的数据的 `_id`
        """
        try:
            collection = self.db[collection_name]
            result = collection.insert_one(data)
            self.logger.debug(f"插入数据成功，插入ID: {result.inserted_id}")
            return result.inserted_id
        except PyMongoError as e:
            self.logger.error(f"插入数据失败: {e}")
            return None

    def insert_many(self, collection_name: str, data_list: list):
        """
        批量插入数据

        :param collection_name: 集合名称
        :param data_list: 插入的文档数据列表
        :return: 插入的文档数量
        """
        try:
            collection = self.db[collection_name]
            result = collection.insert_many(data_list)
            self.logger.debug(f"成功插入 {len(result.inserted_ids)} 条数据")
            return len(result.inserted_ids)
        except PyMongoError as e:
            self.logger.error(f"批量插入数据失败: {e}")
            return 0

    def find(self, collection_name: str, query: dict = None, projection: dict = None, limit: int = 0) -> list[dict]:
        """
        查询数据

        :param collection_name: 集合名称
        :param query: 查询条件，默认为空查询（返回所有文档）
        :param projection: 返回字段，默认为返回所有字段
        :param limit: 限制返回结果的数量
        :return: 查询结果（list）
        """
        try:
            collection = self.db[collection_name]
            cursor = collection.find(query, projection)
            if limit > 0:
                cursor = cursor.limit(limit)
            result = list(cursor)
            self.logger.debug(f"查询到 {len(result)} 条数据")
            return result
        except PyMongoError as e:
            self.logger.error(f"查询数据失败: {e}")
            return []

    def find_one(self, collection_name: str, query: dict) -> dict:
        """
        查询单条数据

        :param collection_name: 集合名称
        :param query: 查询条件
        :return: 查询到的文档（dict）
        """
        try:
            collection = self.db[collection_name]
            result = collection.find_one(query)
            self.logger.debug("查询到一条数据")
            return result
        except PyMongoError as e:
            self.logger.error(f"查询单条数据失败: {e}")
            return None

    def update_one(self, collection_name: str, query: dict, payload: dict, upsert: bool = False):
        """
        更新单条数据

        :param collection_name: 集合名称
        :param query: 查询条件
        :param update_data: 更新的数据
        :param upsert: 如果为 True，当查询不到时将插入新文档
        :return: 更新后的文档（dict）
        """
        try:
            collection = self.db[collection_name]
            result = collection.find_one_and_update(
                query,
                payload,
                return_document=ReturnDocument.AFTER,
                upsert=upsert
            )
            self.logger.debug("更新数据成功")
            return result
        except PyMongoError as e:
            self.logger.error(f"更新数据失败: {e}")
            return None

    def update_many(self, collection_name: str, query: dict, payload: dict):
        """
        更新多条数据

        :param collection_name: 集合名称
        :param query: 查询条件
        :param update_data: 更新的数据
        :return: 更新的文档数量
        """
        try:
            collection = self.db[collection_name]
            result = collection.update_many(query, {"$set": payload})
            self.logger.debug(f"更新了 {result.modified_count} 条数据")
            return result.modified_count
        except PyMongoError as e:
            self.logger.error(f"批量更新数据失败: {e}")
            return 0

    def delete_one(self, collection_name: str, query: dict):
        """
        删除单条数据

        :param collection_name: 集合名称
        :param query: 查询条件
        :return: 删除的文档数量
        """
        try:
            collection = self.db[collection_name]
            result = collection.delete_one(query)
            self.logger.debug(f"删除数据成功: {result.deleted_count} 条")
            return result.deleted_count
        except PyMongoError as e:
            self.logger.error(f"删除数据失败: {e}")
            return 0

    def delete_many(self, collection_name: str, query: dict):
        """
        删除多条数据

        :param collection_name: 集合名称
        :param query: 查询条件
        :return: 删除的文档数量
        """
        try:
            collection = self.db[collection_name]
            result = collection.delete_many(query)
            self.logger.debug(f"删除了 {result.deleted_count} 条数据")
            return result.deleted_count
        except PyMongoError as e:
            self.logger.error(f"删除数据失败: {e}")
            return 0

    def count_documents(self, collection_name: str, query: dict = None):
        """
        统计集合中的文档数量

        :param collection_name: 集合名称
        :param query: 查询条件，默认为空查询（返回所有文档）
        :return: 文档数量
        """
        try:
            collection = self.db[collection_name]
            count = collection.count_documents(query or {})
            self.logger.debug(f"查询到 {count} 条数据")
            return count
        except PyMongoError as e:
            self.logger.error(f"统计数据失败: {e}")
            return 0