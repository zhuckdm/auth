from src.app.services import fill_admin_db
from src.app import api


def test_fill_admin_db():
    check_fill_admin_db(['Test1@gmail.com'])
    check_fill_admin_db(['Test1@gmail.com', 'Test2@gmail.com'])
    check_fill_admin_db(['Test1@gmail.com', 'Test2@gmail.com', 'Test3@gmail.com'])

    admin_mails = [f'TestT{i}@gmail.com' for i in range(1, 31)]
    check_fill_admin_db(admin_mails)


def check_fill_admin_db(admin_mails: list):
    api.admin.delete_all_docs()
    admin = fill_admin_db(api.admin, admin_mails)

    assert admin.get_count() == len(admin_mails)
    for mail in admin_mails:
        mail = mail.lower()
        assert admin.get_doc_by_mail(mail)['mail'] == mail

    admin.delete_all_docs()
