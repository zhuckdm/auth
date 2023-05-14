import time
import pytest
from fastapi.testclient import TestClient
from requests import Response
from datetime import timedelta

from src.app import api
from src.app.services import *


test_users_data = {
    'ivanovii@gmail.com': {
        'family': 'Иванов',
        'name': 'Иван',
        'fathername': 'Иванович',
        'gender': 'М',
        'mail': 'ivanovii@gmail.com',
        'birthday': '31.12.1977'
    },
    'petrovapp@gmail.com': {
        'family': 'Петрова',
        'name': 'Полина',
        'fathername': 'Петоровна',
        'gender': 'Ж',
        'mail': 'petrovapp@gmail.com',
        'birthday': '31.12.1988'
    }
}

client = TestClient(api.app)
config = get_app_config_for_tests()

CORRECT_MAIL = config['smtp']['login']
CORRECT_TEST_MAIL = 'TestMail@gmail.com'
CORRECT_MAIL_IN_STRANGE_CASE = get_line_in_strange_case(CORRECT_MAIL)
INCORRECT_MAIL = 'INCORRECT_MAIL'
TEST_ADMIN_MAIL = 'TestAdminMail@gmail.com'
UNREGISTERED_MAIL = 'UnregisteredMail@gmail.com'
NOT_ASSIGNED_MAIL = 'NotAssignedMail@gmail.com'
NOT_IMPORTANT_CODE = '123456'
NOT_IMPORTANT_AT = 'NOT_IMPORTANT_AT'
NOT_IMPORTANT_RT = 'NOT_IMPORTANT_RT'
USERS_DB_NAME = 'test_users'
api.auth_handler = Auth(config['test_mongodb_url'],
                        config['lifetime_rt'],
                        config['lifetime_at'],
                        config['days_rt_in_black_list'])
ah = api.auth_handler


@pytest.fixture(autouse=True)
def run_before_test():
    clean_db_auth()
    clean_users_and_admin_db()


def test_delete_all_old_rt_when_server_startup():
    black_list = {}
    for i in range(1, 5):
        black_list[i] = {
            'rt': f'rt{i}',
            'mail': f'test{i}@test.test',
            'recording_date': datetime.utcnow() - timedelta(days=33 - i, minutes=1)
        }
        ah.black_list.add_doc(black_list[i])
    check_db_docs_count(rt_count=0, codes=0, black_list=4)

    Auth(config['test_mongodb_url'],
         config['lifetime_rt'],
         config['lifetime_at'],
         days_rt_in_black_list=31)

    check_db_docs_count(rt_count=0, codes=0, black_list=2)
    changed_black_list = ah.black_list.get_all_docs()
    assert len(changed_black_list) == 2
    for i in range(3, 5):
        assert changed_black_list[i]['rt'] == black_list[i]['rt']
        assert changed_black_list[i]['mail'] == black_list[i]['mail']
        assert_equal_datetime(changed_black_list[i]['recording_date'], black_list[i]['recording_date'])


def test_make_rt_without_code_when_login_in_for_first_time():
    response = client.get(f'/refresh-token?mail={CORRECT_MAIL}')

    assert response.status_code == 200
    assert response.json() == {'need_confirmation_code': False}
    check_db_docs_count(rt_count=1, codes=0, black_list=0)


def test_make_good_rt():
    mail = CORRECT_MAIL

    client.get(f'/refresh-token?mail={mail}')
    rt_doc = ah.r_tokens.get_doc_by_mail(mail.lower())

    assert len(rt_doc) == 5
    assert '_id' in rt_doc
    assert rt_doc['mail'] == mail.lower()
    assert type(rt_doc['rt_hash']) == str
    assert len(rt_doc['rt_hash']) == 20
    assert type(rt_doc['rt']) == str
    assert rt_doc['recording_date'] > datetime.utcnow() - timedelta(seconds=2)
    assert rt_doc['recording_date'] < datetime.utcnow() + timedelta(seconds=2)


def test_save_in_db_user_how_login_in_for_first_time():
    mail = CORRECT_TEST_MAIL
    try:
        api.users.delete_doc_by_mail(mail.lower())
    except KeyError:
        pass

    client.get(f'/refresh-token?mail={mail}')

    assert get_user_data_by_mail(api.users, mail) == {'mail': mail.lower()}


def test_get_rt_ignore_case():
    mail = CORRECT_MAIL_IN_STRANGE_CASE
    response = client.get(f'/refresh-token?mail={mail}')
    mail_for_rt_hash = ah.r_tokens.get_doc_by_mail(mail.lower())['mail']

    assert response.status_code == 200
    assert response.json() == {'need_confirmation_code': False}
    assert mail_for_rt_hash == mail.lower()
    check_db_docs_count(rt_count=1, codes=0, black_list=0)


def test_do_not_make_second_rt_but_make_code_when_login_in_for_second_time_quickly():
    mail = CORRECT_MAIL

    client.get(f'/refresh-token?mail={mail}')
    rt_hash = get_rt_hash_from_db_white_list(mail)
    response = client.get(f'/refresh-token?mail={mail}')
    rt_hash_after_second_post = get_rt_hash_from_db_white_list(mail)

    assert response.status_code == 200
    assert response.json() == {'need_confirmation_code': True}
    assert rt_hash == rt_hash_after_second_post
    check_db_docs_count(rt_count=1, codes=1, black_list=0)


def test_make_good_code():
    mail = CORRECT_MAIL

    client.get(f'/refresh-token?mail={mail}')
    client.get(f'/refresh-token?mail={mail}')
    code_doc = ah.confirmation_codes.get_doc_by_mail(mail.lower())

    assert len(code_doc) == 4
    assert '_id' in code_doc
    assert code_doc['mail'] == mail.lower()
    assert type(code_doc['code']) == int
    assert code_doc['code'] > 99999
    assert code_doc['code'] < 1000000
    assert code_doc['recording_date'] > datetime.utcnow() - timedelta(seconds=2)
    assert code_doc['recording_date'] < datetime.utcnow() + timedelta(seconds=2)


def test_do_second_rt_without_code_when_login_in_and_previous_rt_became_old():
    """
    Ввели почту первый раз. На почту пришел refresh token. Прошло время и токен устарел. Ввели почту второй раз.
    Предыдущий токен уходит в black list и на почту приходит новый, код подтверждения не требуется.
    """
    mail = CORRECT_MAIL

    client.get(f'/refresh-token?mail={mail}')
    time.sleep(3)
    old_rt_hash = get_rt_hash_from_db_white_list(mail)
    response = client.get(f'/refresh-token?mail={mail}')
    new_rt_hash = get_rt_hash_from_db_white_list(mail)
    token_from_black_list = get_rt_hash_from_db_black_list(mail)

    assert response.status_code == 200
    assert response.json() == {'need_confirmation_code': False}
    assert new_rt_hash != old_rt_hash
    assert token_from_black_list == old_rt_hash
    check_db_docs_count(rt_count=1, codes=0, black_list=1)


def test_get_new_rt_through_code():
    """
    Ввели почту первый раз. На почту пришел refresh token. Ввели почту второй раз,
    предыдущий refresh token еще актуален. На почту не пришел refresh token, а пришел код подтверждения.
    Ввели почту и код подтверждения. На почту пришел новый refresh token, предыдущий ушел в black list.
    """
    mail = CORRECT_MAIL

    client.get(f'/refresh-token?mail={mail}')
    old_rt_hash = get_rt_hash_from_db_white_list(mail)
    client.get(f'/refresh-token?mail={mail}')
    code = get_code_from_db(mail)
    time.sleep(1)
    response = client.get(f'/refresh-token?mail={mail}&code={code}')
    new_rt_hash = get_rt_hash_from_db_white_list(mail)
    rt_hash_from_black_list = get_rt_hash_from_db_black_list(mail)

    assert response.status_code == 204
    assert new_rt_hash != old_rt_hash
    assert rt_hash_from_black_list == old_rt_hash
    check_db_docs_count(rt_count=1, codes=0, black_list=1)


def test_make_good_rt_for_black_list():
    mail = CORRECT_MAIL

    client.get(f'/refresh-token?mail={mail}')
    old_rt_doc = ah.r_tokens.get_doc_by_mail(mail.lower())
    client.get(f'/refresh-token?mail={mail}')
    code = get_code_from_db(mail)
    time.sleep(1)
    client.get(f'/refresh-token?mail={mail}&code={code}')
    rt_from_black_list_doc = ah.black_list.get_doc_by_mail(mail.lower())

    assert len(rt_from_black_list_doc) == 5
    assert '_id' in rt_from_black_list_doc
    assert rt_from_black_list_doc['mail'] == mail.lower()
    assert rt_from_black_list_doc['rt_hash'] == old_rt_doc['rt_hash']
    assert rt_from_black_list_doc['rt'] == old_rt_doc['rt']
    assert rt_from_black_list_doc['recording_date'] > datetime.utcnow() - timedelta(seconds=2)
    assert rt_from_black_list_doc['recording_date'] < datetime.utcnow() + timedelta(seconds=2)


def test_get_new_rt_through_code_ignore_case():
    mail = CORRECT_MAIL_IN_STRANGE_CASE

    client.get(f'/refresh-token?mail={mail}')
    old_rt_doc = ah.r_tokens.get_doc_by_mail(mail.lower())
    client.get(f'/refresh-token?mail={mail.upper()}')
    code = get_code_from_db(mail)
    time.sleep(1)
    response = client.get(f'/refresh-token?mail={mail}&code={code}')
    new_rt_doc = ah.r_tokens.get_doc_by_mail(mail.lower())
    rt_doc_from_black_list = ah.black_list.get_doc_by_mail(mail.lower())

    assert response.status_code == 204
    assert new_rt_doc['rt_hash'] != old_rt_doc['rt_hash']
    assert rt_doc_from_black_list['rt_hash'] == old_rt_doc['rt_hash']
    assert new_rt_doc['mail'] == mail.lower()
    assert old_rt_doc['mail'] == mail.lower()
    assert rt_doc_from_black_list['mail'] == mail.lower()
    check_db_docs_count(rt_count=1, codes=0, black_list=1)


def test_do_not_get_new_rt_through_code_if_code_has_already_been_used():
    mail = CORRECT_MAIL

    client.get(f'/refresh-token?mail={mail}')
    client.get(f'/refresh-token?mail={mail}')
    code = get_code_from_db(mail)
    client.get(f'/refresh-token?mail={mail}&code={code}')
    response = client.get(f'/refresh-token?mail={mail}&code={code}')

    assert response.status_code == 401
    assert response.json() == {'detail': 'There is no code for this mail. Please request a new code.'}
    check_db_docs_count(rt_count=1, codes=0, black_list=1)


def test_do_not_get_second_rt_but_reset_code_if_code_is_incorrect():
    mail = CORRECT_MAIL

    client.get(f'/refresh-token?mail={mail}')
    client.get(f'/refresh-token?mail={mail}')
    code = int(get_code_from_db(mail))
    code = (code + 1) if code < 999999 else (code - 1)
    code = str(code)
    response = client.get(f'/refresh-token?mail={mail}&code={code}')

    assert response.status_code == 401
    assert response.json() == {
        'detail': 'Invalid code. The current code for this mail has been reset. Please request a new code.'
    }
    check_db_docs_count(rt_count=1, codes=0, black_list=0)


def test_do_not_get_second_rt_if_mail_is_not_assigned():
    mail = CORRECT_MAIL

    client.get(f'/refresh-token?mail={mail}')
    client.get(f'/refresh-token?mail={mail}')
    code = get_code_from_db(mail)
    mail = NOT_ASSIGNED_MAIL
    response = client.get(f'/refresh-token?mail={mail}&code={code}')

    assert response.status_code == 401
    assert response.json() == {'detail': 'There is no code for this mail. Please request a new code.'}
    check_db_docs_count(rt_count=1, codes=1, black_list=0)


def test_get_at_by_valid_and_not_too_old_rt():
    mail = CORRECT_MAIL

    client.get(f'/refresh-token?mail={mail}')
    rt_hash = get_rt_hash_from_db_white_list(mail)
    response = client.get(f'/access-token?refresh_token={rt_hash}')
    at = response.json()['access_token']
    decoded_at = ah.decode_at(at)
    expected_at = form_simple_at_data(mail)

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert_equal_at(decoded_at, expected_at)
    check_db_docs_count(rt_count=1, codes=0, black_list=0)


def test_do_not_get_at_by_invalid_rt():
    mail = CORRECT_MAIL

    client.get(f'/refresh-token?mail={mail}')
    rt_hash = get_rt_hash_from_db_white_list(mail)
    invalid_rt_hash = rt_hash[::-1]
    response = client.get(f'/access-token?refresh_token={invalid_rt_hash}')

    assert response.status_code == 401
    assert response.json() == {'detail': 'Invalid refresh token'}
    check_db_docs_count(rt_count=1, codes=0, black_list=0)


def test_do_not_get_at_by_rt_from_black_list():
    mail = CORRECT_MAIL

    client.get(f'/refresh-token?mail={mail}')
    rt_hash = get_rt_hash_from_db_white_list(mail)
    client.get(f'/refresh-token?mail={mail}')
    code = get_code_from_db(mail)
    client.get(f'/refresh-token?mail={mail}&code={code}')
    response = client.get(f'/access-token?refresh_token={rt_hash}')

    assert response.status_code == 401
    assert response.json() == {'detail': 'Refresh token from the black list'}
    check_db_docs_count(rt_count=1, codes=0, black_list=1)


def test_do_not_get_at_by_expired_rt():
    mail = CORRECT_MAIL

    client.get(f'/refresh-token?mail={mail}')
    rt_hash = get_rt_hash_from_db_white_list(mail)
    time.sleep(3)
    response = client.get(f'/access-token?refresh_token={rt_hash}')

    assert response.status_code == 401
    assert response.json() == {'detail': 'Refresh token expired'}
    check_db_docs_count(rt_count=1, codes=0, black_list=0)


def test_get_at_data_after_check_at():
    mail = CORRECT_MAIL

    at = get_at_through_api(mail)
    response = client.get(f'/check-access-token?access_token={at}')
    decoded_at = response.json()
    expected_at = form_simple_at_data(mail)

    assert response.status_code == 200
    assert_equal_at(decoded_at, expected_at)
    check_db_docs_count(rt_count=1, codes=0, black_list=0)


def test_get_401_if_at_is_invalid_after_check_at():
    mail = CORRECT_MAIL

    invalid_at = get_at_through_api(mail)[::-1]
    response = client.get(f'/check-access-token?access_token={invalid_at}')

    assert response.status_code == 401
    assert response.json() == {'detail': 'Invalid access token'}
    check_db_docs_count(rt_count=1, codes=0, black_list=0)


def test_get_401_if_at_is_expired_after_check_at():
    mail = CORRECT_MAIL

    at = get_at_through_api(mail)
    time.sleep(3)
    response = client.get(f'/check-access-token?access_token={at}')

    assert response.status_code == 401
    assert response.json() == {'detail': 'Access token expired'}
    check_db_docs_count(rt_count=1, codes=0, black_list=0)


def test_get_user_data_if_mail_is_correct():
    check_getting_user_data_by_correct_mail('ivanovii@gmail.com', test_users_data['ivanovii@gmail.com'])
    check_getting_user_data_by_correct_mail('petrovapp@gmail.com', test_users_data['petrovapp@gmail.com'])


def test_get_user_data_if_mail_is_correct_ignore_case():
    check_getting_user_data_by_correct_mail('IvanovII@gmail.com', test_users_data['ivanovii@gmail.com'])
    check_getting_user_data_by_correct_mail('PetrovaPP@gmail.com', test_users_data['petrovapp@gmail.com'])


def test_put_one_fill_of_user_data():
    check_update_user_data({'family': 'Иванов'})


def test_put_some_fills_of_user_data():
    new_data = {
        'family': 'Иванов',
        'fathername': 'Иванович',
        'gender': 'М',
    }
    check_update_user_data(new_data)


def test_put_all_user_data():
    new_data = {
        'family': 'Иванов',
        'name': 'Иван',
        'fathername': 'Иванович',
        'gender': 'М',
        'mail': 'newtest@gmail.com',
        'birthday': '07.04.2023',
    }
    check_update_user_data(new_data)


def test_put_data_after_login_in_for_first_time():
    mail = CORRECT_TEST_MAIL
    client.get(f'/refresh-token?mail={mail}')
    new_data = {'fathername': 'Петрович', 'gender': 'М'}
    new_data_str = str(new_data).replace('\'', '\"')
    updated_data = {'mail': mail.lower()} | new_data

    at = get_admin_at_through_api()
    response = client.put(f'/user-data?access_token={at}&mail={mail}&data={new_data_str}')

    assert response.status_code == 200
    assert response.json() == updated_data
    assert get_user_data_by_mail(api.users, updated_data['mail']) == updated_data


def test_put_data_of_yourself():
    mail = TEST_ADMIN_MAIL
    api.users.add_doc({'mail': mail.lower()})
    api.admin.add_doc({'mail': mail.lower()})
    new_data = {'fathername': 'Петрович', 'gender': 'М'}
    updated_data = {'mail': mail.lower()} | new_data
    new_data_str = str(new_data).replace('\'', '\"')

    at = get_at_through_api(mail)
    response = client.put(f'/user-data?access_token={at}&mail={mail}&data={new_data_str}')

    assert response.status_code == 200
    assert response.json() == updated_data
    assert get_user_data_by_mail(api.users, updated_data['mail']) == updated_data


def test_one_admin_update_data_of_several_users():
    at = get_admin_at_through_api()
    users_mails = [CORRECT_TEST_MAIL, UNREGISTERED_MAIL]
    new_users_data = [{'fathername': 'Петрович', 'gender': 'М'}, {'fathername': 'Семеновна', 'gender': 'Ж'}]
    new_users_data_str = [str(data).replace('\'', '\"') for data in new_users_data]
    for mail in users_mails:
        api.users.add_doc({'mail': mail.lower()})

    for i in range(len(users_mails)):
        updated_users_data = {'mail': users_mails[i].lower()} | new_users_data[i]
        response = client.put(f'/user-data?access_token={at}&mail={users_mails[i]}&data={new_users_data_str[i]}')

        assert response.status_code == 200
        assert response.json() == updated_users_data
        assert get_user_data_by_mail(api.users, updated_users_data['mail']) == updated_users_data


def test_one_admin_update_data_of_user_several_times():
    mail = CORRECT_TEST_MAIL
    at = get_admin_at_through_api()
    api.users.add_doc({'mail': mail.lower()})
    new_users_data = [{'fathername': 'Петрович', 'gender': 'Ж'}, {'gender': 'М'}]
    new_users_data_str = [str(data).replace('\'', '\"') for data in new_users_data]
    updated_users_data = {'mail': mail.lower()}

    for i in range(len(new_users_data)):
        updated_users_data = updated_users_data | new_users_data[i]
        response = client.put(f'/user-data?access_token={at}&mail={mail}&data={new_users_data_str[i]}')

        assert response.status_code == 200
        assert response.json() == updated_users_data
        assert get_user_data_by_mail(api.users, updated_users_data['mail']) == updated_users_data


def test_get_401_if_invalid_at_for_update_user_data():
    mail = CORRECT_MAIL
    invalid_at = get_at_through_api(mail)[::-1]
    new_data_str = str({'family': 'Иванов'}).replace('\'', '\"')
    response = client.put(f'/user-data?access_token={invalid_at}&mail={mail}&data={new_data_str}')

    assert response.status_code == 401
    assert response.json() == {'detail': 'Invalid access token'}
    check_db_docs_count(rt_count=1, codes=0, black_list=0)


def test_get_401_if_expired_at_for_update_user_data():
    mail = CORRECT_MAIL
    at = get_at_through_api(mail)
    time.sleep(3)
    new_data_str = str({'family': 'Иванов'}).replace('\'', '\"')
    response = client.put(f'/user-data?access_token={at}&mail={mail}&data={new_data_str}')

    assert response.status_code == 401
    assert response.json() == {'detail': 'Access token expired'}
    check_db_docs_count(rt_count=1, codes=0, black_list=0)


def test_get_403_if_at_is_not_of_admin_for_update_user_data():
    mail = CORRECT_TEST_MAIL
    at = get_at_through_api(mail)
    new_data_str = str({'family': 'Иванов'}).replace('\'', '\"')
    response = client.put(f'/user-data?access_token={at}&mail={mail}&data={new_data_str}')

    assert response.status_code == 403
    assert response.json() == {'detail': 'Not enough rights'}
    check_db_docs_count(rt_count=1, codes=0, black_list=0)


def test_get_400_if_invalid_data_for_update_user():
    at = get_admin_at_through_api()
    incorrect_data_str = 'incorrect_data'
    response = client.put(f'/user-data?access_token={at}&mail={CORRECT_MAIL}&data={incorrect_data_str}')

    assert response.status_code == 400
    assert response.json() == {'detail': 'Invalid data'}
    check_db_docs_count(rt_count=1, codes=0, black_list=0)


def test_get_400_if_invalid_mail_in_data_for_update_user():
    at = get_admin_at_through_api()
    incorrect_data_str = {'mail': INCORRECT_MAIL}
    response = client.put(f'/user-data?access_token={at}&mail={CORRECT_MAIL}&data={incorrect_data_str}')

    assert response.status_code == 400
    assert response.json() == {'detail': 'Invalid mail in the data'}
    check_db_docs_count(rt_count=1, codes=0, black_list=0)


def test_get_400_if_invalid_mail_of_user_for_update():
    at = get_admin_at_through_api()
    new_data_str = str({'family': 'Иванов'}).replace('\'', '\"')
    response = client.put(f'/user-data?access_token={at}&mail={INCORRECT_MAIL}&data={new_data_str}')

    assert response.status_code == 400
    assert response.json() == {'detail': 'Invalid mail'}
    check_db_docs_count(rt_count=1, codes=0, black_list=0)


def test_get_404_if_unregistered_mail_of_user_for_update():
    at = get_admin_at_through_api()
    new_data_str = str({'family': 'Иванов'}).replace('\'', '\"')
    response = client.put(f'/user-data?access_token={at}&mail={UNREGISTERED_MAIL}&data={new_data_str}')

    assert response.status_code == 404
    assert response.json() == {'detail': 'Unregistered mail'}
    check_db_docs_count(rt_count=1, codes=0, black_list=0)


def test_put_mail_user_and_ignore_case():
    new_data = {'mail': CORRECT_TEST_MAIL.upper()}
    check_update_user_data(new_data)


def test_do_not_get_user_data_if_mail_does_not_exist():
    mail = UNREGISTERED_MAIL

    response = client.get(f'/user-data?mail={mail}')

    assert response.status_code == 404
    assert response.json() == {'detail': 'Unregistered mail'}
    check_db_docs_count(rt_count=0, codes=0, black_list=0)


def test_get_401_if_invalid_scope_for_at():
    check_401_if_invalid_scope_for_at('GET', '/check-access-token')


def test_get_401_if_incorrect_mail():
    check_401_for_incorrect_mail('GET', f'/refresh-token?mail={INCORRECT_MAIL}')
    check_401_for_incorrect_mail('GET', f'/refresh-token?mail={INCORRECT_MAIL}&code={NOT_IMPORTANT_CODE}')
    check_401_for_incorrect_mail('GET', f'/user-data?mail={INCORRECT_MAIL}')


def test_get_500_if_auth_db_is_not_connected():
    check_500_for_not_connected_auth_db('GET', f'/refresh-token?mail={CORRECT_MAIL}')
    check_500_for_not_connected_auth_db('GET', f'/access-token?refresh_token={NOT_IMPORTANT_RT}')
    check_500_for_not_connected_auth_db('GET', f'/check-access-token?access_token={NOT_IMPORTANT_AT}')


def test_get_500_if_users_db_is_not_connected():
    check_500_for_not_connected_users_db('GET', f'/user-data?mail={CORRECT_MAIL}')
    check_500_for_not_connected_users_db('PUT', f'/user-data?'
                                                f'access_token={NOT_IMPORTANT_AT}&mail={CORRECT_MAIL}&data={None}')


def test_get_500_if_admin_db_is_not_connected():
    check_500_for_not_connected_admin_db('PUT', f'/user-data?'
                                                f'access_token={NOT_IMPORTANT_AT}&mail={CORRECT_MAIL}&data={None}')


def check_getting_user_data_by_correct_mail(mail: str, user_data: dict):
    response = client.get(f'/user-data?mail={mail}')

    assert response.status_code == 200
    assert response.json() == user_data
    check_db_docs_count(rt_count=0, codes=0, black_list=0)


def check_401_if_invalid_scope_for_at(method: str, url: str):
    clean_db_auth()
    mail = CORRECT_MAIL

    client.get(f'/refresh-token?mail={mail}')
    rt = get_rt_from_db_white_list(mail)
    url = f'{url}&access_token={rt}' if '?' in url else f'{url}?access_token={rt}'
    response = run_api_method(method, url)

    assert response.status_code == 401
    assert response.json() == {'detail': 'Scope for the access token is invalid'}
    check_db_docs_count(rt_count=1, codes=0, black_list=0)


def check_401_for_incorrect_mail(method: str, url: str):
    clean_db_auth()

    response = run_api_method(method, url)

    assert response.status_code == 401
    assert response.json() == {'detail': 'Invalid mail'}
    check_db_docs_count(rt_count=0, codes=0, black_list=0)


def check_500_for_not_connected_auth_db(method: str, url: str):
    api.auth_handler = Auth('bad_url_to_db',
                            config['lifetime_rt'],
                            config['lifetime_at'],
                            config['days_rt_in_black_list'])

    response = run_api_method(method, url)

    assert response.status_code == 500
    assert response.json() == {'detail': 'No connection to the database, a server restart is required'}

    api.auth_handler = ah


def check_500_for_not_connected_users_db(method: str, url: str):
    users_copy = api.users
    api.users, _ = get_users_and_admin_db('bad_db_url')
    response = run_api_method(method, url)

    assert response.status_code == 500
    assert response.json() == {'detail': 'No connection to the users database, a server restart is required'}

    api.users = users_copy


def check_500_for_not_connected_admin_db(method: str, url: str):
    admin_copy = api.admin
    _, api.admin = get_users_and_admin_db('bad_db_url')
    response = run_api_method(method, url)

    assert response.status_code == 500
    assert response.json() == {'detail': 'No connection to the admin database, a server restart is required'}

    api.users = admin_copy


def check_update_user_data(new_data: dict):
    user_mail = CORRECT_TEST_MAIL
    api.users.add_doc({'mail': user_mail.lower()})
    updated_user_data = {'mail': user_mail.lower()} | new_data
    updated_user_data['mail'] = updated_user_data['mail'].lower()
    new_data_str = str(new_data).replace('\'', '\"')

    at = get_admin_at_through_api()
    response = client.put(f'/user-data?access_token={at}&mail={user_mail}&data={new_data_str}')

    assert response.status_code == 200
    assert response.json() == updated_user_data
    if 'mail' in new_data and new_data['mail'].lower() != user_mail.lower():
        with pytest.raises(KeyError):
            api.users.get_doc_by_mail(user_mail.lower())
    assert get_user_data_by_mail(api.users, updated_user_data['mail']) == updated_user_data

    api.users.delete_doc_by_mail(updated_user_data['mail'])


def check_db_docs_count(rt_count: int, codes: int, black_list: int):
    assert ah.r_tokens.get_count() == rt_count
    assert ah.confirmation_codes.get_count() == codes
    assert ah.black_list.get_count() == black_list


def assert_equal_datetime(datetime_expected: datetime, datetime_actual: datetime):
    """Сравнить datetime с точностью до секунд"""
    assert datetime_expected.year == datetime_actual.year
    assert datetime_expected.month == datetime_actual.month
    assert datetime_expected.day == datetime_actual.day
    assert datetime_expected.hour == datetime_actual.hour
    assert datetime_expected.minute == datetime_actual.minute
    assert datetime_expected.second == datetime_actual.second


def run_api_method(method: str, url: str) -> Response:
    response = None
    method = method.lower()

    if method == 'get':
        response = client.get(url)
    elif method == 'post':
        response = client.get(url)
    elif method == 'put':
        response = client.put(url)
    elif method == 'delete':
        response = client.delete(url)

    return response


def form_simple_at_data(mail: str):
    time_zone_correction = timedelta(hours=5)
    mail = mail.lower()
    return {
        'exp': datetime_to_seconds(
            datetime.utcnow() + time_zone_correction + timedelta(
                days=config['lifetime_at']['days'],
                hours=config['lifetime_at']['hours'],
                minutes=config['lifetime_at']['minutes'],
                seconds=config['lifetime_at']['seconds']
            )),
        'iat': datetime_to_seconds(datetime.utcnow() + time_zone_correction),
        'scope': 'access_token',
        'sub': mail
    }


def assert_equal_at(actual_at: dict, expected_at: dict):
    assert abs(actual_at['exp'] - expected_at['exp']) < 2
    assert abs(actual_at['iat'] - expected_at['iat']) < 2
    assert actual_at['scope'] == expected_at['scope']
    assert actual_at['sub'] == expected_at['sub']


def get_at_through_api(mail: str):
    client.get(f'/refresh-token?mail={mail}')
    rt_hash = get_rt_hash_from_db_white_list(mail.lower())
    return client.get(f'/access-token?refresh_token={rt_hash}').json()['access_token']


def get_admin_at_through_api():
    admin_mail = TEST_ADMIN_MAIL
    api.admin.add_doc({'mail': admin_mail.lower()})
    client.get(f'/refresh-token?mail={admin_mail}')
    rt_hash = get_rt_hash_from_db_white_list(admin_mail)
    return client.get(f'/access-token?refresh_token={rt_hash}').json()['access_token']


def get_code_from_db(mail: str) -> str:
    mail = mail.lower()
    return str(ah.confirmation_codes.get_doc_by_mail(mail)['code'])


def get_rt_from_db_white_list(mail: str) -> str:
    mail = mail.lower()
    return ah.r_tokens.get_doc_by_mail(mail)['rt']


def get_rt_hash_from_db_white_list(mail: str) -> str:
    mail = mail.lower()
    return ah.r_tokens.get_doc_by_mail(mail)['rt_hash']


def get_rt_hash_from_db_black_list(mail: str) -> str:
    mail = mail.lower()
    return ah.black_list.get_doc_by_mail(mail)['rt_hash']


def clean_db_auth():
    ah.confirmation_codes.delete_all_docs()
    ah.r_tokens.delete_all_docs()
    ah.black_list.delete_all_docs()


def clean_users_and_admin_db():
    for mail in [CORRECT_TEST_MAIL, TEST_ADMIN_MAIL, UNREGISTERED_MAIL, NOT_ASSIGNED_MAIL]:
        try:
            api.users.delete_doc_by_mail(mail.lower())
        except KeyError:
            pass
    try:
        api.admin.delete_doc_by_mail(TEST_ADMIN_MAIL.lower())
    except KeyError:
        pass
