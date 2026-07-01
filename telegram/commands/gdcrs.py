from utils.settings import set_setting
from utils.gdcrs_targets import load_gdcrs_targets, add_gdcrs_target, remove_gdcrs_target_by_index, clear_gdcrs_targets
from utils.stock_code import clean_stock_code

def gdcrs_command(args: list, chat_id: str = None) -> str:
    """골든크로스 / 데드크로스를 위한 분봉 설정 및 대상 종목 관리 명령어입니다.
    
    사용법:
      1. 분봉 값 설정:
         gdcrs intv {단기} {장기} (예: gdcrs intv 5 20)
         gdcrs {단기} {장기} (예: gdcrs 5 20)
      2. 감시 대상 추가:
         gdcrs add {종목코드} {금액} (예: gdcrs add 005930 500000)
      3. 감시 대상 목록 조회:
         gdcrs list
      4. 감시 대상 삭제:
         gdcrs remove {번호} (예: gdcrs remove 1)
      5. 감시 대상 목록 비우기:
         gdcrs clear
      6. 실시간 골든크로스 감시 시작/중지: gdcrs start / gdcrs stop
    """
    if not args:
        return (
            "사용법:\n"
            "• 분봉 값 설정: gdcrs intv {단기} {장기} (또는 gdcrs {단기} {장기})\n"
            "• 대상 종목 추가: gdcrs add {종목코드} {금액}\n"
            "• 대상 종목 목록: gdcrs list\n"
            "• 대상 종목 삭제: gdcrs remove {번호}\n"
            "• 대상 종목 목록 비우기: gdcrs clear\n"
            "• 감시 시작: gdcrs start\n"
            "• 감시 중단: gdcrs stop"
        )
        
    subcmd = args[0].strip().lower()
    
    # 1. 대상 종목 추가 (add)
    if subcmd == "add":
        if len(args) < 3:
            return "사용법: gdcrs add {종목코드} {금액}\n예: gdcrs add 005930 500000"
            
        stk_cd = clean_stock_code(args[1].strip())
        if len(stk_cd) != 6 or not stk_cd.isdigit():
            return "종목코드는 6자리 숫자여야 합니다. (예: 005930)"
            
        # 블랙리스트 검사
        from utils.blacklist import BlacklistManager
        if BlacklistManager().is_blacklisted(stk_cd):
            return f"❌ 블랙리스트 제한: 이 종목({stk_cd})은 블랙리스트에 등록되어 있어 골든크로스 감시 대상으로 추가할 수 없습니다."
            
        try:
            amount = int(args[2].strip())
            if amount <= 0:
                return "금액은 1 이상의 정수여야 합니다."
        except ValueError:
            return "금액은 정수로 입력해야 합니다."
            
        success = add_gdcrs_target(stk_cd, amount)
        if success:
            return f"✅ 골든크로스 감시 대상 추가 완료\n- 종목코드: {stk_cd}\n- 설정금액: {amount:,}원"
        else:
            return "❌ 감시 대상 추가 중 오류가 발생했습니다."
            
    # 2. 대상 종목 목록 조회 (list)
    elif subcmd == "list":
        targets = load_gdcrs_targets()
        if not targets:
            return "현재 등록된 골든크로스 감시 대상 종목이 없습니다."
            
        msg_lines = [
            "📈 골든크로스 감시 대상 목록",
            "━━━━━━━━━━━━━━━━━━━"
        ]
        for i, target in enumerate(targets, 1):
            msg_lines.append(f"{i}. 종목코드: {target['stk_cd']} | 금액: {target['amount']:,}원")
        msg_lines.append("━━━━━━━━━━━━━━━━━━━")
        return "\n".join(msg_lines)
        
    # 3. 대상 종목 삭제 (remove)
    elif subcmd == "remove":
        if len(args) < 2:
            return "사용법: gdcrs remove {번호}\n예: gdcrs remove 1"
            
        try:
            index = int(args[1].strip())
        except ValueError:
            return "번호는 정수로 입력해야 합니다."
            
        success, removed = remove_gdcrs_target_by_index(index)
        if success and removed:
            return f"✅ 골든크로스 감시 대상 삭제 완료\n- 종목코드: {removed['stk_cd']}\n- 설정금액: {removed['amount']:,}원"
        else:
            return f"❌ 해당 번호({index})의 항목을 찾을 수 없거나 삭제에 실패했습니다."
            
    # 3.5. 대상 종목 전체 삭제 (clear)
    elif subcmd == "clear":
        success = clear_gdcrs_targets()
        if success:
            return "✅ 골든크로스 감시 대상 목록이 모두 비워졌습니다."
        else:
            return "❌ 감시 대상 목록 비우기 중 오류가 발생했습니다."

    # 4. 분봉 값 설정 (intv 혹은 숫자 기입 분기)
    elif subcmd == "intv":
        if len(args) < 3:
            return "사용법: gdcrs intv {단기} {장기}\n예: gdcrs intv 5 20"
        short_str = args[1].strip()
        long_str = args[2].strip()
        return _set_intervals(short_str, long_str)
        
    elif subcmd == "start":
        from realtime.gdcrs_runner import GDCRSManager
        manager = GDCRSManager()
        res = manager.start(chat_id)
        return res if res else "✅ 골든크로스 감시가 실행되었습니다."

    elif subcmd == "stop":
        from realtime.gdcrs_runner import GDCRSManager
        manager = GDCRSManager()
        return manager.stop()

    elif not subcmd.isdigit():
        return (
            "올바르지 않은 명령 또는 인수 유형입니다.\n"
            "사용법:\n"
            "• 분봉 값 설정: gdcrs intv {단기} {장기} (또는 gdcrs {단기} {장기})\n"
            "• 대상 종목 추가: gdcrs add {종목코드} {금액}\n"
            "• 대상 종목 목록: gdcrs list\n"
            "• 대상 종목 삭제: gdcrs remove {번호}\n"
            "• 대상 종목 목록 비우기: gdcrs clear\n"
            "• 감시 시작: gdcrs start\n"
            "• 감시 중단: gdcrs stop"
        )

        
    else:
        # gdcrs {단기} {장기} 형식 처리
        if len(args) < 2:
            return "사용법: gdcrs {단기} {장기}\n예: gdcrs 5 20"
        short_str = args[0].strip()
        long_str = args[1].strip()
        return _set_intervals(short_str, long_str)

def _set_intervals(short_str: str, long_str: str) -> str:
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
