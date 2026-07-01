from utils.settings import set_setting, get_setting

def mxhold_command(args: list, chat_id: str = None) -> str:
    """
    'mxhold' 명령어를 처리하여 최대 보유 종목 수 설정을 변경합니다.
    
    사용법:
    1. mxhold {개수} : 최대 보유 종목 수를 {개수}로 설정 (예: mxhold 5)
    2. mxhold 0 : 제한 없음
    """
    if not args:
        return (
            "사용법:\n"
            "• mxhold {개수} : 최대 보유 종목 수 제한 설정 (예: mxhold 5)\n"
            "• mxhold 0 : 제한 없음"
        )
        
    try:
        count = int(args[0].strip())
        if count < 0:
            return "최대 보유 종목 수는 0 이상의 정수여야 합니다."
    except ValueError:
        return "최대 보유 종목 수는 정수로 입력해야 합니다."
        
    set_setting("max_holdings", count)
    
    if count == 0:
        return "✅ 최대 보유 종목 수 제한이 해제되었습니다 (무제한)."
    else:
        return f"✅ 최대 보유 종목 수 제한 설정 완료: 최대 {count}개"
