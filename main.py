import sys
import os
import logging

# 프로젝트 루트 디렉토리를 sys.path에 추가하여 모듈을 원활히 찾을 수 있게 함
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telegram.bot import start_polling, reply_message
from utils.scheduler import start_scheduler
from config.config import telegram_chat_id
from api.auth import request_access_token
from api.session import session

def main():
    # 로그 레벨 기본값 정보로 출력
    logging.info("ai-stock 자동매매 시스템 시작")
    
    # 텔레그램 시작 알림 전송
    if telegram_chat_id:
        reply_message(telegram_chat_id, "ai-stock 프로그램이 시작되었습니다.")
        
    # 모의투자 모드로 자동 로그인
    logging.info("모의투자 모드로 자동 로그인을 시도합니다...")
    auth_res = request_access_token("paper")
    if auth_res["success"]:
        session.update(
            token=auth_res["token"],
            mode="paper",
            host_url=auth_res["host_url"],
            chat_id=telegram_chat_id
        )
        logging.info("모의투자 모드 로그인 성공!")
        if telegram_chat_id:
            reply_message(telegram_chat_id, "모의투자 자동 로그인에 성공했습니다.")
    else:
        logging.error(f"모의투자 모드 로그인 실패: {auth_res.get('error_msg')}")
        if telegram_chat_id:
            reply_message(telegram_chat_id, f"모의투자 자동 로그인에 실패했습니다: {auth_res.get('error_msg')}")
            
    try:
        start_scheduler()
        start_polling()
    except KeyboardInterrupt:
        logging.info("키보드 인터럽트에 의해 프로그램이 종료되었습니다.")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

if __name__ == "__main__":
    main()
