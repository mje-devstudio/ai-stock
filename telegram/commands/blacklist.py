from utils.blacklist import BlacklistManager

def blacklist_command(args: list, chat_id: str = None) -> str:
    """
    'blacklist' 명령어를 처리합니다.
    
    사용법:
    1. blacklist add {종목코드} : 종목 추가
    2. blacklist list : 일련번호와 함께 항목 확인
    3. blacklist remove {일련번호} : 항목 삭제
    """
    if not args:
        return (
            "사용법:\n"
            "• blacklist add {종목코드} : 블랙리스트 종목 추가\n"
            "• blacklist list : 블랙리스트 목록 확인\n"
            "• blacklist remove {일련번호} : 블랙리스트 항목 삭제"
        )
        
    sub_cmd = args[0].strip().lower()
    
    if sub_cmd == "add":
        if len(args) < 2:
            return "추가할 종목코드를 입력해주세요. (예: blacklist add 005930)"
        stk_cd = args[1].strip()
        success, msg = BlacklistManager().add(stk_cd)
        if success:
            return f"✅ {msg}"
        else:
            return f"❌ {msg}"
            
    elif sub_cmd == "list":
        lst = BlacklistManager().list()
        if not lst:
            return "📁 현재 등록된 블랙리스트 종목이 없습니다."
            
        msg_lines = [
            "🚫 블랙리스트 등록 종목 목록",
            "━━━━━━━━━━━━━━━━━━━"
        ]
        for idx, cd in enumerate(lst, 1):
            msg_lines.append(f"{idx}. {cd}")
        msg_lines.append("━━━━━━━━━━━━━━━━━━━")
        return "\n".join(msg_lines)
        
    elif sub_cmd == "remove":
        if len(args) < 2:
            return "삭제할 항목의 일련번호를 입력해주세요. (예: blacklist remove 1)"
        try:
            idx = int(args[1].strip())
        except ValueError:
            return "일련번호는 정수여야 합니다."
        success, msg = BlacklistManager().remove_by_index(idx)
        if success:
            return f"✅ {msg}"
        else:
            return f"❌ {msg}"
            
    else:
        return "알 수 없는 서브 명령어입니다. (사용 가능: add, list, remove)"
