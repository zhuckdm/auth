import yaml
import json
from datetime import datetime

from src.app.auth import Auth
from src.app.collection import Collection
from src.app.db import SimpleMongoDB
from src.app.exceptions_services import get_no_connection_if_timeout_error
from src.app.fake_mail_messenger import FakeEmailMessenger
from src.app.mail_messenger import MailMessenger


def get_app_src(config: dict):
    if config['use_test_db']:
        users, admin = get_users_and_admin_db(config['test_mongodb_url'], 'test_')
        users.delete_all_docs()
        admin.delete_all_docs()
        users = fill_users_db(users, 'users_test.json')
        auth_handler = Auth(
            config['test_mongodb_url'],
            config['lifetime_rt'],
            config['lifetime_at'],
            config['days_rt_in_black_list']
        )
    else:
        users, admin = get_users_and_admin_db(config['mongodb_url'])
        if users.is_empty():
            users = fill_users_db(users, 'users.json')
        auth_handler = Auth(
            config['mongodb_url'],
            config['lifetime_rt'],
            config['lifetime_at'],
            config['days_rt_in_black_list']
        )

    if admin.is_empty():
        admin = fill_admin_db(admin, config['admin_mails'])

    if config['use_fake_mail_messenger']:
        messenger = FakeEmailMessenger(config['smtp'])
    else:
        messenger = MailMessenger(config['smtp'])

    return users, admin, auth_handler, messenger


def get_app_config() -> dict:
    with open('config.yml', 'r') as config_yaml:
        config = yaml.load(config_yaml, Loader=yaml.SafeLoader)
    return config


def get_users_and_admin_db(db_url: str, prefix: str = ''):
    db = SimpleMongoDB(db_url, f'{prefix}users_db')
    db.connect()
    users = get_no_connection_if_timeout_error(db.get_collection, f'{prefix}users')
    admin = get_no_connection_if_timeout_error(db.get_collection, f'{prefix}admin')
    return users, admin


def fill_users_db(users, path):
    if type(users) == Collection:
        with open(path, 'r') as users_json:
            users_dict = json.load(users_json)
        for user in users_dict:
            user['mail'] = user['mail'].lower()
            users.add_doc(user)
    return users


def fill_admin_db(admin, admin_mails: list):
    if type(admin) == Collection:
        [admin.add_doc({'mail': mail.lower()}) for mail in admin_mails]
    return admin


def get_user_data_by_mail(users: Collection, mail: str):
    mail = mail.lower()
    user_with_id = users.get_doc_by_mail(mail)
    user_without_id = {}
    for key in user_with_id:
        if key != '_id':
            user_without_id[key] = user_with_id[key]
    return user_without_id


def update_user(mail: str, data: dict, users: Collection):
    if 'mail' in data:
        data['mail'] = data['mail'].lower()
    users.put_doc_by_mail(mail, data)


def add_user_if_it_is_not_in_db(mail: str, users: Collection):
    mail = mail.lower()
    try:
        users.get_doc_by_mail(mail)
    except KeyError:
        users.add_doc({'mail': mail})


def get_app_config_for_tests() -> dict:
    config = get_app_config()
    config['lifetime_rt']['days'] = 0
    config['lifetime_rt']['hours'] = 0
    config['lifetime_rt']['minutes'] = 0
    config['lifetime_rt']['seconds'] = 2  # Для проверок, что у токенов истекло время жизни
    config['lifetime_at'] = config['lifetime_rt'].copy()
    config['days_rt_in_black_list'] = 31
    return config


def get_line_in_strange_case(line: str) -> str:
    return line[:len(line) // 2].lower() + line[len(line) // 2:].upper()


def datetime_to_seconds(dt: datetime):
    return int(dt.timestamp())
