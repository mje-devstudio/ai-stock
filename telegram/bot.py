import time
import requests
import logging
import queue
import threading
from config.config import telegram_token, telegram_chat_id
from telegram.commands import dispatch_command

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ai-stock.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# 전역 메시지 큐 생성
_message_queue = queue.Queue()

def _message_sender_worker():
    """백그라운드에서 큐를 감시하며 메시지를 순차적으로 전송합니다."""
    logging.info("텔레그램 메시지 전송 백그라운드 스레드가 시작되었습니다.")
    while True:
        try:
            # 큐에서 대기 (블로킹)
            chat_id, text = _message_queue.get()
            
            # 실제 텔레그램 API 전송 수행
            _send_telegram_api(chat_id, text)
            
            # 전송 완료 처리
            _message_queue.task_done()
            
            # API 제한을 피하기 위해 짧은 지연시간(100ms) 추가
            time.sleep(0.1)
        except Exception as e:
            logging.error(f"메시지 전송 워커 스레드 오류 발생: {e}")
            time.sleep(1)

def _send_telegram_api(chat_id: str, text: str):
    """실제로 텔레그램 HTTP POST API를 호출합니다."""
    if not telegram_token:
        logging.error("telegram_token이 설정되지 않았습니다.")
        return
        
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code != 200:
            logging.error(f"메시지 전송 실패 (HTTP {res.status_code}): {res.text}")
    except Exception as e:
        logging.error(f"메시지 전송 중 오류 발생: {e}")

# 워커 스레드 기동
_sender_thread = threading.Thread(target=_message_sender_worker, daemon=True)
_sender_thread.start()

def reply_message(chat_id: str, text: str):
    """메시지 큐에 전송할 메시지를 집어넣고 즉시 리턴합니다 (Non-blocking)."""
    if not chat_id or not text:
        return
    _message_queue.put((chat_id, text))

def start_polling():
    """텔레그램 메시지 수신 폴링 루프를 시작합니다."""
    if not telegram_token:
        logging.error("telegram_token이 없으므로 폴링을 시작할 수 없습니다.")
        return

    logging.info("텔레그램 봇 폴링 루프를 시작합니다...")
    # 기존에 남아 있는 메시지를 건너뛰기 위해 최신 업데이트 ID 기준으로 offset 초기화
    try:
        init_url = f"https://api.telegram.org/bot{telegram_token}/getUpdates"
        init_res = requests.get(init_url, params={"limit": 1, "timeout": 0}, timeout=10)
        if init_res.status_code == 200:
            init_updates = init_res.json().get("result", [])
            if init_updates:
                offset = init_updates[-1]["update_id"] + 1
            else:
                offset = None
        else:
            offset = None
    except Exception as e:
        logging.error(f"텔레그램 초기 offset 설정 중 오류 발생: {e}")
        offset = None

    while True:
        try:
            url = f"https://api.telegram.org/bot{telegram_token}/getUpdates"
            params = {
                "timeout": 20,  # 롱 폴링 대기 시간 (초)
            }
            if offset is not None:
                params["offset"] = offset

            # 텔레그램 업데이트 가져오기 (타임아웃은 timeout + 여유분)
            res = requests.get(url, params=params, timeout=30)

            if res.status_code == 409:
                logging.error("Conflict: 다른 봇 인스턴스가 실행 중일 수 있습니다. 10초 대기 후 재시도...")
                time.sleep(10)
                continue
            elif res.status_code != 200:
                logging.error(f"업데이트 수신 실패 (HTTP {res.status_code}): {res.text}")
                time.sleep(5)
                continue

            # 정상 응답
            updates = res.json().get("result", [])
            for update in updates:
                update_id = update.get("update_id")
                offset = update_id + 1
                # 메시지 객체 추출 (일반 메시지만 처리, 채널 포스트 등 제외)
                message = update.get("message")
                if not message:
                    continue
                chat = message.get("chat", {})
                chat_id = chat.get("id")
                text = message.get("text", "")
                if not text or not chat_id:
                    continue
                logging.info(f"메시지 수신 - ChatID: {chat_id}, Text: {text}")
                # 명령어 실행 및 응답 전송
                response_text = dispatch_command(text, chat_id=chat_id)
                reply_message(chat_id, response_text)
                    
                
        except KeyboardInterrupt:
            logging.info("사용자에 의해 폴링 루프가 종료되었습니다.")
            break
        except Exception as e:
            logging.error(f"폴링 중 예외 발생: {e}")
            time.sleep(5)
