from datetime import datetime, timedelta


class Collection:
    __name = ""
    __db_collection = None
    __id_counter = 0

    def __init__(self, collection_name, db_collection):
        self.__name = collection_name
        self.__db_collection = db_collection
        self.__update_id_counter()

    def get_name(self):
        return self.__name

    def add_doc(self, doc: dict):
        self.__index_doc(doc)
        self.__db_collection.insert_one(doc)

    def add_docs(self, docs: list):
        self.__index_docs(docs)
        self.__db_collection.insert_many(docs)

    def get_doc_by_id(self, doc_id: int) -> dict:
        return self.__get_doc_by_id_or_key_error(doc_id)

    def get_doc_by_mail(self, mail: str) -> dict:
        return self.__get_doc_by_mail_or_key_error(mail)

    def get_doc_by_rt_hash(self, rt_hash: str):
        return self.__get_doc_by_rt_hash_or_key_error(rt_hash)

    def get_count(self) -> int:
        return len(self.get_all_docs())

    def get_all_docs(self) -> dict:
        result = {}
        for doc in self.__db_collection.find():
            result[doc['_id']] = doc
        return result

    def is_empty(self) -> bool:
        return self.get_count() == 0

    def put_doc_by_id(self, doc_id: int, new_param: dict):
        self.__get_doc_by_id_or_key_error(doc_id)
        self.__db_collection.update_one({'_id': doc_id}, {'$set': new_param})

    def put_doc_by_mail(self, mail: str, data: dict):
        self.__get_doc_by_mail_or_key_error(mail)
        self.__db_collection.update_one({'mail': mail}, {'$set': data})

    def delete_doc_by_id(self, doc_id: int):
        self.__get_doc_by_id_or_key_error(doc_id)
        self.__db_collection.delete_one({'_id': doc_id})

    def delete_all_docs_by_mail(self, mail: str):
        self.__db_collection.delete_many({'mail': mail})

    def delete_doc_by_mail(self, mail: str):
        self.__get_doc_by_mail_or_key_error(mail)
        self.__db_collection.delete_one({'mail': mail})

    def delete_all_docs(self):
        self.__db_collection.delete_many({})
        self.__id_counter = 0

    def delete_all_old_docs(self, date_field: str, days: int):
        """
        Удалить все документы, которые старше указанного количества дней.
        Параметры:
        date_field : поле документа с типом Date
        days : старше какого количества дней должна быть дата, для удаления документа
        """
        deadline = datetime.utcnow() - timedelta(days=days)
        self.__db_collection.delete_many({date_field: {'$lt': deadline}})

    def __update_id_counter(self):
        last_doc = self.__db_collection.find_one({'$query': {}, '$orderby': {'_id': -1}})
        self.__id_counter = 0 if last_doc is None else last_doc['_id']

    def __index_docs(self, docs: list):
        for doc in docs:
            self.__index_doc(doc)

    def __index_doc(self, doc: dict):
        doc['_id'] = self.__id_prefix_increment()

    def __id_prefix_increment(self):
        self.__id_counter += 1
        return self.__id_counter

    def __get_doc_by_id_or_key_error(self, doc_id: int):
        doc = self.__db_collection.find_one({'_id': doc_id})
        if doc is None:
            raise KeyError('Item not found')
        return doc

    def __get_doc_by_mail_or_key_error(self, mail):
        doc = self.__db_collection.find_one({'mail': mail})
        if doc is None:
            raise KeyError('Item not found')
        return doc

    def __get_doc_by_rt_hash_or_key_error(self, rt_hash: str):
        doc = self.__db_collection.find_one({'rt_hash': rt_hash})
        if doc is None:
            raise KeyError('Item not found')
        return doc
