from api.order import sell_stock
from api.stock import get_account_evaluation
from utils.stock_code import clean_stock_code

def sell_command(args: list, chat_id: str = None) -> str:
    """
    'sell' 명령어를 처리합니다.
    사용법:
    sell {보유종목} {수량}
    예: sell 삼성전자 10
    예: sell 005930 10
    """
    if len(args) < 2:
        return "사용법: sell {종목코드|종목명} {수량}\n예: sell 삼성전자 10\n예: sell 005930 10"
        
    stk_input = clean_stock_code(args[0].strip())
    
    try:
        ord_qty = int(args[1].strip())
        if ord_qty <= 0:
            return "수량은 1 이상의 정수여야 합니다."
    except ValueError:
        return "수량은 정수로 입력해야 합니다."
        
    # 종목 식별
    stk_cd = None
    stk_nm = stk_input
    
    if len(stk_input) == 6 and stk_input.isdigit():
        stk_cd = stk_input
        # 코드로 입력한 경우 이름을 찾기 위해 계좌 조회를 시도
        eval_res = get_account_evaluation()
        if eval_res["success"]:
            for h in eval_res["holdings"]:
                raw_cd = h.get("stk_cd", "")
                short_cd = clean_stock_code(raw_cd)
                if short_cd == stk_cd:
                    stk_nm = h.get("stk_nm", stk_input)
                    break
    else:
        # 이름으로 입력한 경우 계좌 조회하여 코드로 변환
        eval_res = get_account_evaluation()
        if not eval_res["success"]:
            return f"보유종목 조회를 실패하여 종목명을 코드로 변환할 수 없습니다.\n- 사유: {eval_res['error_msg']}"
            
        holdings = eval_res["holdings"]
        for h in holdings:
            if h.get("stk_nm") == stk_input:
                raw_cd = h.get("stk_cd", "")
                stk_cd = clean_stock_code(raw_cd)
                stk_nm = h.get("stk_nm")
                break
                
        if not stk_cd:
            return f"보유종목 중 '{stk_input}'을(를) 찾을 수 없습니다. 정확한 종목명 또는 6자리 종목코드를 입력해주세요."

    # 매도 실행
    res = sell_stock(stk_cd, ord_qty)
    
    if not res["success"]:
        return f"매도 주문 실패\n- 사유: {res['error_msg']}"
        
    data = res["data"]
    body = data.get("body", data)
    
    ord_no = body.get("ord_no", "")
    return_code = body.get("return_code")
    return_msg = body.get("return_msg", "")
    
    if return_code == 0:
        msg = (
            f"✅ 매도 주문 성공\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"종목명: {stk_nm}\n"
            f"종목코드: {stk_cd}\n"
            f"주문수량: {ord_qty:,}주\n"
            f"주문단가: 시장가\n"
            f"주문번호: {ord_no}\n"
            f"메시지: {return_msg}\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        return msg
    else:
        return f"매도 주문 접수 오류: {return_msg} (코드: {return_code})"
