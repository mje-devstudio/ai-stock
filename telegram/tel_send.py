import os
import sys
import requests

# 프로젝트 루트 디렉토리를 sys.path에 추가 (직접 실행 시 ModuleNotFoundError 방지)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import telegram_token, telegram_chat_id


def send_message(text: str) -> dict:
    """주어진 메시지를 텔레그램으로 보냅니다."""
    if not telegram_token or not telegram_chat_id:
        print("Error: telegram_token 또는 telegram_chat_id가 설정되지 않았습니다.")
        return {}

    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {
        "chat_id": telegram_chat_id,
        "text": text,
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"텔레그램 메시지 전송 실패 (Code: {response.status_code})")
            print(response.text)
            return response.json()
    except Exception as e:
        print("텔레그램 전송 중 오류 발생:", e)
        return {}


if __name__ == "__main__":
    # 테스트용 전송
    test_msg = "텔레그램 메시지 전송 테스트입니다."
    print("메시지 전송을 시도합니다...")
    res = send_message(test_msg)
    if res.get("ok"):
        print("성공적으로 메시지를 보냈습니다.")
    else:
        print("메시지 전송 실패")
