from utils.settings import set_setting, get_setting

def time_command(args: list, chat_id: str = None) -> str:
    """
    'time' 명령어를 처리하여 매수 주문 미체결 시 자동 처리(취소 또는 시장가 정정) 설정을 변경합니다.
    
    사용법:
    1. time {s} cancel : 매수 후 {s}초 동안 미체결 시 주문을 자동 취소합니다.
    2. time {s} market : 매수 후 {s}초 동안 미체결 시 호가를 1틱씩 올려 재주문합니다. (시장가 도달까지 반복)
    3. time 0 [cancel/market] : 미체결 자동 처리 기능을 비활성화합니다.
    """
    if len(args) < 2:
        return (
            "사용법:\n"
            "• time {초} cancel : {초}초 동안 미체결 시 주문 취소\n"
            "• time {초} market : {초}초 동안 미체결 시 호가를 1틱씩 상향 재주문\n"
            "• time 0 [cancel/market] : 기능 비활성화"
        )
        
    try:
        seconds = int(args[0].strip())
        if seconds < 0:
            return "시간(초)은 0 이상의 정수여야 합니다."
    except ValueError:
        return "시간(초)은 정수로 입력해야 합니다."
        
    action = args[1].strip().lower()
    if action not in ["cancel", "market"]:
        return "액션은 'cancel' 또는 'market'이어야 합니다."
        
    # 설정 저장
    set_setting("order_timeout_seconds", seconds)
    set_setting("order_timeout_action", action)
    
    if seconds == 0:
        return f"✅ 매수 주문 미체결 자동 처리 기능이 비활성화되었습니다."
    else:
        action_kr = "자동 취소" if action == "cancel" else "1틱씩 상향 재주문"
        return (
            f"✅ 매수 주문 미체결 자동 처리 설정 완료\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"• 대기 시간: {seconds}초\n"
            f"• 미체결 시 액션: {action_kr} ({action})\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
