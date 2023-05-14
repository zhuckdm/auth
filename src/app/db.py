from pymongo import MongoClient
from src.app.collection import Collection


class SimpleMongoDB:
    __collections = None
    __db_client = None
    __db_name = ""
    __url = ""

    def __init__(self, url: str, db_name='SimpleDB'):
        self.__url = url
        self.__db_name = db_name

    def get_name(self):
        return self.__db_name

    def get_url(self):
        return self.__url

    def connect(self):
        self.__db_client = MongoClient(self.__url, serverSelectionTimeoutMS=5000)
        self.__collections = self.__db_client[self.__db_name]

    def get_collection(self, collection_name: str):
        return Collection(collection_name, self.__collections[collection_name])

    def disconnect(self):
        self.__db_client.close()
