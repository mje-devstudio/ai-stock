import time
import datetime
import threading
import logging
from api.session import session
from api.auth import request_access_token
from utils.settings import get_setting
from config.config import telegram_token, telegram_chat_id

def send_notification(text: str):
    """터미널에 출력하고 텔레그램으로도 보냅니다."""
    # 터미널 출력
    logging.info(text)
    
    # 텔레그램 메시지 전송
    if not telegram_token:
        logging.error("telegram_token이 설정되지 않아 알림을 보낼 수 없습니다.")
        return
        
    chat_id = getattr(session, "chat_id", None) or telegram_chat_id
    if not chat_id:
        logging.error("대화방 Chat ID(session.chat_id 또는 telegram_chat_id)가 없어 알림을 보낼 수 없습니다.")
        return
        
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    try:
        import requests
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code != 200:
            logging.error(f"텔레그램 알림 전송 실패 (HTTP {res.status_code}): {res.text}")
    except Exception as e:
        logging.error(f"텔레그램 알림 전송 중 오류 발생: {e}")

def scheduler_loop():
    logging.info("스케줄러 루프를 시작합니다.")
    last_renewal_date = None
    next_renewal_retry_time = None
    last_gdcrs_restart_date = None
    last_ddcrs_restart_date = None
    last_stls_restart_date = None
    
    while True:
        try:
            now = datetime.datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            current_time_str = now.strftime("%H:%M")
            
            # 1. 평일 장 시작 시간 골든크로스 감시 자동 재시작
            market_start_time = get_setting("market_start_time") or "09:00"
            if current_time_str == market_start_time and now.weekday() < 5 and last_gdcrs_restart_date != today_str:
                if get_setting("gdcrs_active", False):
                    send_notification("⏰ 평일 장 시작 시간이 되어 골든크로스 감시를 자동 재기동합니다...")
                    try:
                        from realtime.gdcrs_runner import GDCRSManager
                        manager = GDCRSManager()
                        if manager.active:
                            manager.stop()
                        start_res = manager.start()
                        send_notification(f"🔄 골든크로스 재기동 결과: {start_res}")
                        last_gdcrs_restart_date = today_str
                    except Exception as gdcrs_err:
                        send_notification(f"❌ 골든크로스 자동 재기동 실패: {gdcrs_err}")
                else:
                    last_gdcrs_restart_date = today_str

            # 1.1. 평일 장 시작 시간 데드크로스 감시 자동 재시작
            if current_time_str == market_start_time and now.weekday() < 5 and last_ddcrs_restart_date != today_str:
                if get_setting("ddcrs_active", False):
                    send_notification("⏰ 평일 장 시작 시간이 되어 데드크로스 감시를 자동 재기동합니다...")
                    try:
                        from realtime.ddcrs_runner import DDCRSManager
                        manager = DDCRSManager()
                        if manager.active:
                            manager.stop()
                        start_res = manager.start()
                        send_notification(f"🔄 데드크로스 재기동 결과: {start_res}")
                        last_ddcrs_restart_date = today_str
                    except Exception as ddcrs_err:
                        send_notification(f"❌ 데드크로스 자동 재기동 실패: {ddcrs_err}")
                else:
                    last_ddcrs_restart_date = today_str

            # 1.2. 평일 장 시작 시간 스탑로스 감시 자동 재시작
            if current_time_str == market_start_time and now.weekday() < 5 and last_stls_restart_date != today_str:
                if get_setting("stls_active", False):
                    send_notification("⏰ 평일 장 시작 시간이 되어 스탑로스 감시를 자동 재기동합니다...")
                    try:
                        from realtime.stls_runner import STLSManager
                        manager = STLSManager()
                        if manager.active:
                            manager.stop()
                        start_res = manager.start()
                        send_notification(f"🔄 스탑로스 재기동 결과: {start_res}")
                        last_stls_restart_date = today_str
                    except Exception as stls_err:
                        send_notification(f"❌ 스탑로스 자동 재기동 실패: {stls_err}")
                else:
                    last_stls_restart_date = today_str



            
            # 1. 토큰 자동 갱신 체크
            renewal_time = get_setting("renewal_time") or "08:55"
            
            trigger_renewal = False
            if current_time_str == renewal_time and last_renewal_date != today_str:
                trigger_renewal = True
            elif next_renewal_retry_time is not None and now >= next_renewal_retry_time:
                trigger_renewal = True
                
            if trigger_renewal:
                if session.is_logged_in():
                    mode_kr = "모의투자" if session.mode == "paper" else "실투자"
                    send_notification(f"[{mode_kr}] 설정된 시간({renewal_time})이 되어 토큰 자동 갱신을 진행합니다...")
                    
                    res = request_access_token(session.mode)
                    if res["success"]:
                        session.update(token=res["token"], mode=session.mode, host_url=res["host_url"])
                        masked_token = f"{res['token'][:10]}...{res['token'][-10:]}" if len(res['token']) > 20 else res['token']
                        send_notification(
                            f"[{mode_kr}] 토큰 자동 갱신 완료!\n"
                            f"- 새 토큰: {masked_token}\n"
                            f"- 갱신 완료 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        last_renewal_date = today_str
                        next_renewal_retry_time = None
                    else:
                        send_notification(
                            f"[{mode_kr}] 토큰 자동 갱신 실패!\n"
                            f"- 사유: {res['error_msg']}\n"
                            f"5분 후 다시 갱신을 시도합니다."
                        )
                        next_renewal_retry_time = now + datetime.timedelta(minutes=5)
                        last_renewal_date = today_str
                else:
                    logging.info(f"자동 갱신 시간({renewal_time})이 되었으나 로그인 상태가 아닙니다. 갱신을 건너뜁니다.")
                    last_renewal_date = today_str
                    next_renewal_retry_time = None
                    
            # 2. 예약된 명령 체크 및 실행
            from utils.reservations import load_reservations, save_reservations
            reservations = load_reservations()
            if reservations:
                rsv_changed = False
                rsvs_to_keep = []
                for rsv in reservations:
                    is_once = rsv.get("once", False)
                    is_time_match = (rsv["time"] == current_time_str)
                    is_not_run_today = (rsv.get("last_run_date") != today_str)
                    is_weekday_or_once = (is_once or now.weekday() < 5)
                    
                    if is_time_match and is_not_run_today and is_weekday_or_once:
                        cmd_text = rsv["command"]
                        rsv_id = rsv["id"]
                        
                        once_label = " (1회성)" if is_once else ""
                        send_notification(f"🔔 [예약 실행] {rsv['time']}에 예약된 명령 '{cmd_text}'을(를) 실행합니다.{once_label} (ID: {rsv_id})")
                        
                        try:
                            from telegram.commands import dispatch_command
                            chat_id = getattr(session, "chat_id", None) or telegram_chat_id
                            response = dispatch_command(cmd_text, chat_id=chat_id)
                            send_notification(response)
                        except Exception as cmd_err:
                            send_notification(f"❌ [예약 실행 실패] 명령어 실행 중 오류 발생: {cmd_err}")
                            
                        if is_once:
                            rsv_changed = True
                            continue
                        else:
                            rsv["last_run_date"] = today_str
                            rsv_changed = True
                            
                    rsvs_to_keep.append(rsv)
                    
                if rsv_changed:
                    save_reservations(rsvs_to_keep)
                    
            # 30초마다 체크
            time.sleep(30)
        except Exception as e:
            logging.error(f"스케줄러 작동 중 예외 발생: {e}")
            time.sleep(30)

def start_scheduler():
    """백그라운드에서 스케줄러 스레드를 시작합니다."""
    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()
