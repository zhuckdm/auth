import hashlib
import random
import jwt
from datetime import datetime, timedelta
from fastapi import HTTPException

from src.app.collection import Collection
from src.app.db import SimpleMongoDB
from src.app.exceptions_services import get_no_connection_if_timeout_error


class Auth:
    __secret = ''
    algorithm = 'HS256'
    db = None
    r_tokens = None
    black_list = None
    confirmation_codes = None
    __lifetime_rt = {}
    __lifetime_at = {}
    days_rt_in_black_list = 0
    __HASH_SIZE = 20

    def __init__(self, mongodb_url: str, lifetime_rt: dict, lifetime_at: dict, days_rt_in_black_list: int):
        self.db = SimpleMongoDB(mongodb_url, 'auth_collections')
        self.__lifetime_rt = lifetime_rt
        self.__lifetime_at = lifetime_at
        self.days_rt_in_black_list = days_rt_in_black_list
        self.db.connect()
        self.r_tokens = get_no_connection_if_timeout_error(self.db.get_collection, 'r_tokens')
        self.black_list = get_no_connection_if_timeout_error(self.db.get_collection, 'black_list')
        self.__delete_all_old_rt()
        self.confirmation_codes = get_no_connection_if_timeout_error(self.db.get_collection, 'confirmation_codes')
        self.__generate_new_secret()

    def get_500_if_db_is_not_connected(self):
        # TODO Нужна проверка, не только, что связи с БД нет изначально, а то, что связь есть, но потом исчезла.
        for collection in [self.r_tokens, self.black_list, self.confirmation_codes]:
            if collection == "No connection":
                raise HTTPException(status_code=500,
                                    detail="No connection to the database, a server restart is required")

    def encode_at(self, mail):
        payload = {
            'exp': datetime.utcnow() + timedelta(
                days=self.__lifetime_at['days'],
                hours=self.__lifetime_at['hours'],
                minutes=self.__lifetime_at['minutes'],
                seconds=self.__lifetime_at['seconds']),
            'iat': datetime.utcnow(),
            'scope': 'access_token',
            'sub': mail
        }
        return jwt.encode(payload, self.__secret, algorithm=self.algorithm)

    def decode_at(self, at: str):
        """
        Проверить, что access token валидный,
        в случае успеха вернуть данные токена,
        иначе ошибку 401
        """
        self.__get_401_if_invalid_at(at)
        payload = jwt.decode(at, self.__secret, algorithms=[self.algorithm])
        return payload

    def get_mail_by_at(self, at: str):
        """
        Проверить, что access token валидный,
        в случае успеха вернуть почту, за которой закреплен этот токен,
        иначе ошибку 401
        """
        return self.decode_at(at)['sub']

    def get_new_rt_hash(self, mail: str) -> str:
        """Выполнение подготовительных операций для получения refresh token и выдача его hash"""
        self.__if_rt_by_mail_exists_add_it_to_black_list(mail)
        self.confirmation_codes.delete_all_docs_by_mail(mail)
        rt = self.__encode_rt(mail).decode('UTF-8')
        rt_hash = hashlib.sha224(rt.encode('utf-8')).hexdigest()[:self.__HASH_SIZE]
        self.r_tokens.add_doc({
            'rt_hash': rt_hash,
            'rt': rt,
            'mail': mail,
            'recording_date': datetime.utcnow()
        })
        return rt_hash

    def get_new_code_for_mail(self, mail: str) -> int:
        """Выполнение подготовительных операций для получения кода подтверждения и выдача его"""
        self.confirmation_codes.delete_all_docs_by_mail(mail)
        code = random.randint(100001, 999999)
        self.confirmation_codes.add_doc({
            'code': code,
            'mail': mail,
            'recording_date': datetime.utcnow()
        })
        return code

    def refresh_at(self, rt_hash: str):
        """
        Проверить, что refresh token валидный,
        в случае успеха вернуть новый access_token,
        иначе ошибку 401
        """
        self.__get_401_if_invalid_rt_hash(rt_hash)
        mail = self.r_tokens.get_doc_by_rt_hash(rt_hash)['mail']
        new_at = self.encode_at(mail)
        return new_at

    def is_valid_rt_for_mail(self, mail: str) -> bool:
        """Проверить, что для указанной почты существует валидный refresh token"""
        result = True
        try:
            rt_hash = self.r_tokens.get_doc_by_mail(mail)['rt_hash']
            self.__get_401_if_invalid_rt_hash(rt_hash)
        except(HTTPException, KeyError):
            result = False
        return result

    def get_401_if_there_is_no_code_for_this_mail(self, mail: str):
        try:
            self.confirmation_codes.get_doc_by_mail(mail)
        except KeyError:
            raise HTTPException(status_code=401,
                                detail='There is no code for this mail. Please request a new code.')

    def get_401_and_reset_code_if_it_is_invalid(self, mail: str, code: str):
        doc = self.confirmation_codes.get_doc_by_mail(mail)

        if doc['code'] != int(code):
            self.confirmation_codes.delete_all_docs_by_mail(mail)
            raise HTTPException(status_code=401,
                                detail='Invalid code. '
                                       'The current code for this mail has been reset. '
                                       'Please request a new code.')

    def __encode_rt(self, mail: str):
        payload = {
            'exp': datetime.utcnow() + timedelta(
                days=self.__lifetime_rt['days'],
                hours=self.__lifetime_rt['hours'],
                minutes=self.__lifetime_rt['minutes'],
                seconds=self.__lifetime_rt['seconds']),
            'iat': datetime.utcnow(),
            'scope': 'refresh_token',
            'sub': mail
        }
        return jwt.encode(payload, self.__secret, algorithm=self.algorithm)

    def __if_rt_by_mail_exists_add_it_to_black_list(self, mail: str):
        try:
            rt_doc = self.r_tokens.get_doc_by_mail(mail)
            self.r_tokens.delete_doc_by_mail(mail)
            self.black_list.add_doc({
                'rt_hash': rt_doc['rt_hash'],
                'rt': rt_doc['rt'],
                'mail': mail,
                'recording_date': datetime.utcnow()
            })
        except KeyError:
            pass

    def __get_401_if_invalid_at(self, at: str):
        try:
            payload = jwt.decode(at, self.__secret, algorithms=[self.algorithm])
            if payload['scope'] != 'access_token':
                raise HTTPException(status_code=401, detail='Scope for the access token is invalid')
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail='Access token expired')
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail='Invalid access token')

    def __get_401_if_invalid_rt_hash(self, rt_hash: str):
        try:
            if self.black_list.get_doc_by_rt_hash(rt_hash) is not None:
                raise HTTPException(status_code=401, detail='Refresh token from the black list')
        except KeyError:
            pass

        try:
            rt = self.r_tokens.get_doc_by_rt_hash(rt_hash)['rt']
        except KeyError:
            raise HTTPException(status_code=401, detail='Invalid refresh token')

        try:
            jwt.decode(rt.encode('UTF-8'), self.__secret, algorithms=[self.algorithm])
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail='Refresh token expired')
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail='Invalid refresh token')

    def __delete_all_old_rt(self):
        if type(self.black_list) == Collection:
            self.black_list.delete_all_old_docs(date_field='recording_date', days=self.days_rt_in_black_list)

    def __generate_new_secret(self):
        self.__secret = hashlib.sha512(str(random.random()).encode('utf-8')).hexdigest()
