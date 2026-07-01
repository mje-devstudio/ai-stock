import logging
from utils.settings import get_all_settings, reset_to_default_settings

def stts_command(args: list, chat_id: str = None) -> str:
    """설정된 모든 세팅값을 출력하거나 디폴트로 되돌리는 명령어입니다.
    
    사용법:
      1. 설정 확인: stts
      2. 설정 초기화: stts default
    """
    if args and args[0].lower() == "default":
        if reset_to_default_settings():
            settings = get_all_settings()
            prefix = "✅ 모든 세팅값이 디폴트로 복원되었습니다.\n\n"
        else:
            return "❌ 세팅값을 디폴트로 복원하는 중 오류가 발생했습니다."
    else:
        settings = get_all_settings()
        prefix = ""
        
    key_descriptions = {
        "renewal_time": "토큰 자동 갱신 시간",
        "market_start_time": "장 시작 시간",
        "market_end_time": "장 종료 시간",
        "take_profit_ratio": "익절 기준 (%)",
        "stop_loss_ratio": "손절 기준 (%)",
        "gdcrs_short": "골든크로스 단기 분봉",
        "gdcrs_long": "골든크로스 장기 분봉",
        "ddcrs_short": "데드크로스 단기 분봉",
        "ddcrs_long": "데드크로스 장기 분봉",
        "gdcrs_active": "골든크로스 감시 활성화",
        "ddcrs_active": "데드크로스 감시 활성화",
        "stls_active": "스탑로스 감시 활성화",
        "jggs_active": "조건검색 감시 활성화",
        "trailing_stop_drop_ratio": "트레일링 스탑 고점 대비 하락율 (%)",
        "trailing_stop_min_profit": "트레일링 스탑 최소 발동 수익률 (%)",
        "order_timeout_seconds": "매수 주문 미체결 감시 시간 (초)",
        "order_timeout_action": "매수 주문 미체결 액션",
        "cooldown_hours": "매도 후 재매수 제한 시간 (시간)"
    }
    
    msg_lines = [
        "⚙️ 현재 설정 현황",
        "━━━━━━━━━━━━━━━━━━━"
    ]
    
    # 순서를 보장하거나 정렬하여 보여주기 위해 key_descriptions에 등록된 키를 우선으로 나열
    processed_keys = set()
    for key, desc in key_descriptions.items():
        if key in settings:
            val = settings[key]
            if isinstance(val, bool):
                val_str = "활성화" if val else "비활성화"
            else:
                val_str = str(val)
            msg_lines.append(f"• {desc} ({key}): {val_str}")
            processed_keys.add(key)
            
    # 그 외 다른 동적 설정값도 출력
    for key, value in settings.items():
        if key not in processed_keys:
            val_str = "활성화" if value is True else ("비활성화" if value is False else str(value))
            msg_lines.append(f"• {key} ({key}): {val_str}")

            
    msg_lines.append("━━━━━━━━━━━━━━━━━━━")
    
    return prefix + "\n".join(msg_lines)
