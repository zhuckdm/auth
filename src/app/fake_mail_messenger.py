class FakeEmailMessenger:
    """Заглушка для тестов, чтобы не использовать настоящий mail сервис"""

    def __init__(self, mail_config: dict):
        pass

    def send_code_for_receipt_rt(self, mail: str, code: int):
        pass

    def send_rt_hash(self, mail: str, rt_hash: str):
        pass
