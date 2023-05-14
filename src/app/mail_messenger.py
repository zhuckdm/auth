import smtplib
from email.mime.text import MIMEText


class MailMessenger:
    __login = ''
    __password = ''
    __port = 0
    __MSG_END = 'Письмо сформировано автоматически, пожалуйста, не отвечайте на него.'

    def __init__(self, smtp_config: dict):
        self.__login = smtp_config['login']
        self.__password = smtp_config['password']
        self.__port = smtp_config['port']

    def send_code_for_receipt_rt(self, mail: str, code: int):
        """Отправка кода подтверждения на указанный mail для получения refresh token"""
        subject = 'Ваш код подтверждения'
        body = f"""
Код подтверждения, чтобы получить токен доступа:<br>
<h3>{code}</h3>
Если вы не запрашивали код, проигнорируйте это сообщение.<br>
{self.__MSG_END}
"""
        self.__send_mail(subject, body, mail)

    def send_rt_hash(self, mail: str, rt_hash: str):
        """Отправка refresh token на указанный mail"""
        subject = 'Ваш токен доступа'
        body = f"""
Токен доступа:<br> 
<h3>{rt_hash}</h3>
Если вы не запрашивали токен, проигнорируйте это сообщение.<br> 
{self.__MSG_END}
"""
        self.__send_mail(subject, body, mail)

    def __send_mail(self, subject: str, body: str, mail_receiver: str):
        msg = MIMEText(body, 'html')
        msg['From'] = self.__login
        msg['To'] = mail_receiver
        msg['Subject'] = subject

        with smtplib.SMTP_SSL('smtp.gmail.com', self.__port) as smtp:
            smtp.login(self.__login, self.__password)
            smtp.send_message(msg)
