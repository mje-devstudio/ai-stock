from utils.settings import set_setting, get_setting

def cooldown_command(args: list, chat_id: str = None) -> str:
    """
    'cooldown' 명령어를 처리하여 매도 후 재매수 제한 시간(시간 단위) 설정을 변경합니다.
    
    사용법:
    1. cooldown {시간} : 매도 후 {시간} 동안 재매수 불가 (예: cooldown 24)
    2. cooldown 0 : 쿨다운 제한 비활성화
    """
    if not args:
        return (
            "사용법:\n"
            "• cooldown {시간} : 매도 후 지정된 {시간} 동안 재매수 감시 (예: cooldown 24)\n"
            "• cooldown 0 : 기능 비활성화"
        )
        
    try:
        hours = float(args[0].strip())
        if hours < 0:
            return "쿨다운 시간은 0 이상의 숫자여야 합니다."
    except ValueError:
        return "쿨다운 시간은 숫자로 입력해야 합니다."
        
    set_setting("cooldown_hours", hours)
    
    if hours == 0:
        return "✅ 매도 후 재매수 쿨다운 제한이 비활성화되었습니다."
    else:
        return f"✅ 매도 후 재매수 쿨다운 설정 완료: {hours}시간"
