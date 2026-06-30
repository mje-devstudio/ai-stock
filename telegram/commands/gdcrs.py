from utils.settings import set_setting

def gdcrs_command(args: list, chat_id: str = None) -> str:
    """골든크로스 / 데드크로스를 위한 두 분봉 값을 지정하는 명령어입니다.
    
    사용법:
      gdcrs intv {단기} {장기}
      예: gdcrs intv 5 20 (단기 5, 장기 20으로 설정)
      예: gdcrs 5 20 (단기 5, 장기 20으로 설정)
    """
    if not args:
        return "사용법: gdcrs intv {단기} {장기}\n예: gdcrs intv 5 20"
        
    if args[0].lower() == "intv":
        if len(args) < 3:
            return "사용법: gdcrs intv {단기} {장기}\n예: gdcrs intv 5 20"
        short_str = args[1].strip()
        long_str = args[2].strip()
    elif not args[0].isdigit():
        return f"올바르지 않은 인수 유형입니다. 'intv' 오타인지 확인해 주세요.\n사용법: gdcrs intv {{단기}} {{장기}} 또는 gdcrs {{단기}} {{장기}}"
    else:
        if len(args) < 2:
            return "사용법: gdcrs intv {단기} {장기}\n예: gdcrs intv 5 20"
        short_str = args[0].strip()
        long_str = args[1].strip()
        
    try:
        short_val = int(short_str)
        long_val = int(long_str)
    except ValueError:
        return "단기 및 장기 값은 정수여야 합니다."
        
    if not (1 <= short_val <= 60) or not (1 <= long_val <= 60):
        return "단기 및 장기 값은 1에서 60 사이의 정수여야 합니다."
        
    if short_val >= long_val:
        return "단기 분봉 값은 장기 분봉 값보다 작아야 합니다."
        
    s1 = set_setting("gdcrs_short", short_val)
    s2 = set_setting("gdcrs_long", long_val)
    
    if s1 and s2:
        return f"✅ 골든/데드크로스 분봉 설정 완료\n━━━━━━━━━━━━━━━━━━━\n• 단기 분봉: {short_val}분\n• 장기 분봉: {long_val}분\n━━━━━━━━━━━━━━━━━━━"
    else:
        return "❌ 설정 저장 중 오류가 발생했습니다."
