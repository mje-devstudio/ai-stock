import sys
import logging

def power_off_command(args, chat_id: str = None) -> str:
    """텔레그램에서 'power off' 혹은 'poweroff' 명령을 받으면 프로그램을 종료합니다.

    Args:
        args: 명령어 뒤에 붙는 추가 파라미터 (사용되지 않음).
        chat_id: 응답을 보낼 채팅 ID (옵션).

    Returns:
        문자열 메시지는 반환되지 않으며, 시스템 종료를 수행합니다.
    """
    # 로그 남기기
    logging.info("Power off 명령을 수신했습니다. 프로그램을 종료합니다.")
    # 여기서 바로 프로그램을 종료합니다.
    sys.exit(0)
