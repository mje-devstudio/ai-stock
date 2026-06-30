class SessionState:
    def __init__(self):
        self.token = None
        self.mode = None  # "paper" or "real"
        self.host_url = None
        self.chat_id = None

    def update(self, token: str, mode: str, host_url: str, chat_id: str = None):
        self.token = token
        self.mode = mode
        self.host_url = host_url
        if chat_id is not None:
            self.chat_id = chat_id

    def clear(self):
        self.token = None
        self.mode = None
        self.host_url = None
        self.chat_id = None

    def is_logged_in(self) -> bool:
        return self.token is not None

    def __str__(self):
        return f"SessionState(logged_in={self.is_logged_in()}, mode={self.mode}, host={self.host_url})"

# 전역 세션 객체
session = SessionState()
