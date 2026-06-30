import logging
from realtime.stls_runner import STLSManager
from realtime.gdcrs_runner import GDCRSManager
from realtime.ddcrs_runner import DDCRSManager

logger = logging.getLogger(__name__)

def start_command(args: list, chat_id: str = None) -> str:
    """스탑로스, 골든크로스 또는 데드크로스 감시를 시작합니다.
    사용법: 
      start stls
      start gdcrs
      start ddcrs
    """
    if not args:
        return "사용법이 올바르지 않습니다.\n사용법: start [stls|gdcrs|ddcrs]"
        
    target = args[0].lower().strip()
    if target == "stls":
        manager = STLSManager()
        return manager.start(chat_id)
    elif target == "gdcrs":
        manager = GDCRSManager()
        return manager.start(chat_id)
    elif target == "ddcrs":
        manager = DDCRSManager()
        return manager.start(chat_id)
    else:
        return f"알 수 없는 감시 대상입니다: {target}\n사용법: start [stls|gdcrs|ddcrs]"

def stop_command(args: list, chat_id: str = None) -> str:
    """스탑로스, 골든크로스 또는 데드크로스 감시를 중단합니다.
    사용법: 
      stop stls
      stop gdcrs
      stop ddcrs
    """
    if not args:
        return "사용법이 올바르지 않습니다.\n사용법: stop [stls|gdcrs|ddcrs]"
        
    target = args[0].lower().strip()
    if target == "stls":
        manager = STLSManager()
        return manager.stop()
    elif target == "gdcrs":
        manager = GDCRSManager()
        return manager.stop()
    elif target == "ddcrs":
        manager = DDCRSManager()
        return manager.stop()
    else:
        return f"알 수 없는 감시 대상입니다: {target}\n사용법: stop [stls|gdcrs|ddcrs]"


