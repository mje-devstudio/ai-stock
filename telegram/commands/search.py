from api.stock import get_stock_info
from utils.stock_code import clean_stock_code

def search_command(args: list, chat_id: str = None) -> str:
    """
    'srch' 명령어를 처리합니다.
    사용법: srch {종목코드}
    예: srch 005930
    """
    if not args:
        return "종목코드를 입력해주세요. (예: srch 005930)"
    
    stk_cd = clean_stock_code(args[0].strip())
    
    if len(stk_cd) != 6 or not stk_cd.isdigit():
        return "종목코드는 6자리 숫자여야 합니다. (예: 005930)"

    # 블랙리스트 검사
    from utils.blacklist import BlacklistManager
    if BlacklistManager().is_blacklisted(stk_cd):
        return f"❌ 블랙리스트 제한: 이 종목({stk_cd})은 블랙리스트에 등록되어 있어 조회할 수 없습니다."
    
    res = get_stock_info(stk_cd)
    
    if not res["success"]:
        return f"종목 조회 실패\n- 사유: {res['error_msg']}"
    
    data = res["data"]
    body = data.get("body", data)
    
    code = body.get("stk_cd", stk_cd)
    name = body.get("stk_nm", "")
    
    if not name and body.get("return_code") != 0:
        return f"종목 조회 오류: {body.get('return_msg', '알 수 없는 오류')}"
        
    def safe_int(val_str, default="-"):
        if not val_str: return default
        try:
            return f"{int(val_str):,}"
        except ValueError:
            return val_str
            
    cur_prc = safe_int(body.get("cur_prc"))
    trde_qty = safe_int(body.get("trde_qty"))
    open_pric = safe_int(body.get("open_pric"))
    high_pric = safe_int(body.get("high_pric"))
    low_pric = safe_int(body.get("low_pric"))
    pred_rt = body.get("pred_rt", "-")
    flu_rt = body.get("flu_rt", "-")
    
    msg = (
        f"📊 종목 시세 정보 [{code}]\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏢 종목명: {name}\n"
        f"💰 현재가: {cur_prc}원\n"
        f"📈 전일대비: {pred_rt} ({flu_rt}%)\n"
        f"📊 거래량: {trde_qty}주\n"
        f"🌅 시가: {open_pric}원\n"
        f"🔺 고가: {high_pric}원\n"
        f"🔻 저가: {low_pric}원\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )
    
    return msg
