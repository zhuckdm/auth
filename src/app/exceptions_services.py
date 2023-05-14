import json
import re

from email_validator import validate_email, EmailNotValidError, EmailSyntaxError
from fastapi import HTTPException
from pymongo.errors import ServerSelectionTimeoutError

from src.app.collection import Collection


def get_404_if_key_error(funk, *args):
    try:
        return funk(*args)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=repr(e))


def get_no_connection_if_timeout_error(funk, *args):
    try:
        return funk(*args)
    except ServerSelectionTimeoutError:
        return "No connection"


def get_401_if_invalid_mail(mail: str):
    """Проверяет электронную почту на базовое написание, в случае несоответствия выдаст ошибку 401"""
    mail = mail.lower()

    if len(re.findall(r'[а-яё]', mail)):
        raise HTTPException(status_code=401, detail='Invalid mail')

    try:
        validate_email(mail, check_deliverability=False)
    except (EmailNotValidError, EmailSyntaxError):
        raise HTTPException(status_code=401, detail='Invalid mail')


def get_400_if_invalid_mail(mail: str):
    try:
        get_401_if_invalid_mail(mail)
    except HTTPException:
        raise HTTPException(status_code=400, detail='Invalid mail')


def get_403_if_is_not_admin(admin: Collection, mail: str):
    try:
        admin.get_doc_by_mail(mail)
    except KeyError:
        raise HTTPException(status_code=403, detail='Not enough rights')


def get_data_for_update_or_400(data: str) -> dict:
    try:
        data = data.replace('\'', '\"')
        result = json.loads(data)
    except json.decoder.JSONDecodeError:
        raise HTTPException(status_code=400, detail='Invalid data')
    if 'mail' in result:
        try:
            get_400_if_invalid_mail(result['mail'])
        except HTTPException:
            raise HTTPException(status_code=400, detail='Invalid mail in the data')
    return result


def get_404_if_unregistered_mail(mail: str, users: Collection):
    mail = mail.lower()
    try:
        users.get_doc_by_mail(mail)
    except KeyError:
        raise HTTPException(status_code=404, detail='Unregistered mail')


def get_500_if_users_db_is_not_connected(users):
    if type(users) == str and users == 'No connection':
        raise HTTPException(status_code=500,
                            detail='No connection to the users database, a server restart is required')


def get_500_if_admin_db_is_not_connected(admin):
    if type(admin) == str and admin == 'No connection':
        raise HTTPException(status_code=500,
                            detail='No connection to the admin database, a server restart is required')
