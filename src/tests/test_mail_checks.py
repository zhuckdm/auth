import pytest
from fastapi import HTTPException

from src.app.exceptions_services import get_401_if_invalid_mail


def test_not_get_401_if_standard_mail():
    check_for_good_mail('test@gmail.com')
    check_for_good_mail('test.t@gmail.com')
    check_for_good_mail('test-t@gmail.com')
    check_for_good_mail('test@yandex.ru')


def test_not_get_401_if_standard_mail_with_numbers():
    check_for_good_mail('test1@gmail.com')
    check_for_good_mail('t1est@gmail.com')
    check_for_good_mail('t1es2t3@gmail.com')
    check_for_good_mail('t1234567@gmail.com')


def test_not_get_401_if_standard_mail_with_uppercase_letters():
    check_for_good_mail('TestTT@gmail.com')
    check_for_good_mail('TESTTT@gmail.com')
    check_for_good_mail('test1tt@GMAIL.COM')
    check_for_good_mail('TESTTT@GMAIL.COM')
    check_for_good_mail('Test1TT@gmail.com')
    check_for_good_mail('teSt1@gmail.com')
    check_for_good_mail('test1tT@gmail.com')
    check_for_good_mail('test1tt@Gmail.com')
    check_for_good_mail('test1tt@gmAil.com')
    check_for_good_mail('test1tt@gmaiL.com')
    check_for_good_mail('test1tt@gmail.Com')
    check_for_good_mail('test1tt@gmail.cOm')
    check_for_good_mail('test1tt@gmail.coM')


def test_get_401_if_nonstandard_mail():
    check_for_bad_mail('@gmail.com')
    check_for_bad_mail('test1tt@.com')
    check_for_bad_mail('test1tt@gmail.')
    check_for_bad_mail('test1ttgmail.com')
    check_for_bad_mail('test1tt@gmailcom')
    check_for_bad_mail('test1tt@@gmail.com')
    check_for_bad_mail('test1@tt@gmail.com')
    check_for_bad_mail('test1tt-gmail-com')
    check_for_bad_mail('test1tt.gmail@com')


def test_get_401_if_has_cyrillic():
    check_for_bad_mail('ЖTest1TT@gmail.com')
    check_for_bad_mail('Test1йTT@gmail.com')
    check_for_bad_mail('Test1TTя@gmail.com')
    check_for_bad_mail('Test1TT@эgmail.com')
    check_for_bad_mail('Test1TT@gpщmail.com')
    check_for_bad_mail('Test1TT@gmailя.com')
    check_for_bad_mail('Test1TT@gmail.юcom')
    check_for_bad_mail('Test1TT@gmail.cчom')
    check_for_bad_mail('Test1TT@gmail.comы')
    check_for_bad_mail('лучшая@чаша.py')
    check_for_bad_mail('ЖTesTTя@вgpыmail.яcэomы')
    check_for_bad_mail('ёtest@gmail.com')
    check_for_bad_mail('teёst@gmail.com')
    check_for_bad_mail('testё@gmail.com')
    check_for_bad_mail('test@ёgmail.com')
    check_for_bad_mail('test@gmёail.com')
    check_for_bad_mail('test@gmailё.com')
    check_for_bad_mail('test@gmail.ёcom')
    check_for_bad_mail('test@gmail.cёom')
    check_for_bad_mail('test@gmail.comё')


def check_for_good_mail(mail: str):
    assert get_401_if_invalid_mail(mail) is None


def check_for_bad_mail(mail: str):
    with pytest.raises(HTTPException) as e:
        get_401_if_invalid_mail(mail)
    assert e.value.status_code == 401
    assert e.value.detail == 'Invalid mail'
