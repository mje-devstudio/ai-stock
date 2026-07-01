from api.stock import get_conditional_search_list

def conditional_search_command(args: list, chat_id: str = None) -> str:
    """
    'cond' 명령어를 처리합니다.
    사용법: cond
    """
    res = get_conditional_search_list()
    
    if not res["success"]:
        return f"조건식 목록 조회 실패\n- 사유: {res['error_msg']}"
    
    data = res["data"]
    body = data.get("body", data)
    
    cnsr_list = body.get("data", [])
    if not cnsr_list:
        return (
            "📋 내 조건식 목록\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "등록된 조건식이 없습니다.\n"
            "━━━━━━━━━━━━━━━━━━━"
        )
    
    msg_lines = [
        "📋 내 조건식 목록",
        "━━━━━━━━━━━━━━━━━━━"
    ]
    
    for idx, item in enumerate(cnsr_list):
        if isinstance(item, list) and len(item) >= 2:
            seq = item[0]
            name = item[1]
        elif isinstance(item, dict):
            seq = item.get("seq", "-")
            name = item.get("name", "-")
        else:
            continue
        msg_lines.append(f"[{seq}] : {name}")
        
    msg_lines.append("━━━━━━━━━━━━━━━━━━━")
    return "\n".join(msg_lines)
