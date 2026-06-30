import logging
from realtime.stls_runner import STLSManager

logger = logging.getLogger(__name__)

def start_command(args: list, chat_id: str = None) -> str:
    """스탑로스 감시를 시작합니다.
    사용법: start stls
    """
    if not args or args[0].lower() != "stls":
        return "사용법이 올바르지 않습니다.\n사용법: start stls"
        
    manager = STLSManager()
    return manager.start(chat_id)

def stop_command(args: list, chat_id: str = None) -> str:
    """스탑로스 감시를 중단합니다.
    사용법: stop stls
    """
    if not args or args[0].lower() != "stls":
        return "사용법이 올바르지 않습니다.\n사용법: stop stls"
        
    manager = STLSManager()
    return manager.stop()
