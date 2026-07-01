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
        
        # 세션 모드에 따라 HTTP rate limit 조정
        # 모의투자: 초당 5건 한도 → 안전값 4
        # 실전투자: 초당 20건 한도 → 안전값 16
        from utils.http_queue import set_global_max
        mode_max = 4 if session.mode == "paper" else 16
        set_global_max(mode_max)
        logging.info(f"HTTP rate limit 설정: {mode_max}건/초 (모드: {session.mode})")
        if telegram_chat_id:
            reply_message(telegram_chat_id, "모의투자 자동 로그인에 성공했습니다.")
            
        # 기존에 활성화되어 있던 실시간 감시 서비스 자동 시작
        from utils.settings import get_setting
        
        if get_setting("stls_active", False):
            try:
                from realtime.stls_runner import STLSManager
                res = STLSManager().start()
                logging.info(f"스탑로스 감시 자동 시작: {res}")
                if res:
                    reply_message(telegram_chat_id, f"🔄 {res}")
            except Exception as e:
                logging.error(f"스탑로스 감시 자동 시작 실패: {e}")
                
        if get_setting("gdcrs_active", False):
            try:
                from realtime.gdcrs_runner import GDCRSManager
                res = GDCRSManager().start()
                logging.info(f"골든크로스 감시 자동 시작: {res}")
                if res:
                    reply_message(telegram_chat_id, f"🔄 {res}")
            except Exception as e:
                logging.error(f"골든크로스 감시 자동 시작 실패: {e}")
                
        if get_setting("ddcrs_active", False):
            try:
                from realtime.ddcrs_runner import DDCRSManager
                res = DDCRSManager().start()
                logging.info(f"데드크로스 감시 자동 시작: {res}")
                if res:
                    reply_message(telegram_chat_id, f"🔄 {res}")
            except Exception as e:
                logging.error(f"데드크로스 감시 자동 시작 실패: {e}")
                
        if get_setting("jggs_active", False):
            try:
                from realtime.jggs_runner import JGGSManager
                res = JGGSManager().start()
                logging.info(f"조건검색 감시 자동 시작: {res}")
                if res:
                    reply_message(telegram_chat_id, f"🔄 {res}")
            except Exception as e:
                logging.error(f"조건검색 감시 자동 시작 실패: {e}")

        if get_setting("trst_active", False):
            try:
                from realtime.trst_runner import TRSTManager
                res = TRSTManager().start()
                logging.info(f"트레일링 스탑 감시 자동 시작: {res}")
                if res:
                    reply_message(telegram_chat_id, f"🔄 {res}")
            except Exception as e:
                logging.error(f"트레일링 스탑 감시 자동 시작 실패: {e}")
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
