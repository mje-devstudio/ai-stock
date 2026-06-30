from api.order import buy_stock
from api.stock import get_stock_basic_info
from utils.stock_code import clean_stock_code

def buy_command(args: list, chat_id: str = None) -> str:
    """
    'buy' 명령어를 처리합니다.
    사용법: 
    buy {종목코드} {수량} : 시장가 매수
    buy {종목코드} {수량} {지정가} : 지정가 매수
    buy {종목코드} max {금액} : 최대 금액 기준 시장가 매수
    예: buy 005930 10 (삼성전자 10주 시장가 매수)
    예: buy 005930 10 80000 (삼성전자 10주 80,000원 지정가 매수)
    예: buy 005930 max 500000 (삼성전자 50만원 한도 내 최대 매수)
    """
    if len(args) < 2:
        return "사용법:\n- 수량 기준: buy {종목코드} {수량} [지정가]\n- 금액 기준: buy {종목코드} max {금액}\n예: buy 005930 10\n예: buy 005930 max 500000"
    
    stk_cd = clean_stock_code(args[0].strip())
    
    if len(stk_cd) != 6 or not stk_cd.isdigit():
        return "종목코드는 6자리 숫자여야 합니다. (예: 005930)"
        
    # 최대 금액 기준 매수 처리 (buy {종목코드} max {금액})
    if args[1].strip().lower() == "max":
        if len(args) < 3:
            return "사용법: buy {종목코드} max {금액}\n예: buy 005930 max 500000"
            
        try:
            max_amount = int(args[2].strip())
            if max_amount <= 0:
                return "최대 금액은 1 이상의 정수여야 합니다."
        except ValueError:
            return "최대 금액은 정수로 입력해야 합니다."
            
        # 현재가 조회 (ka10001)
        info_res = get_stock_basic_info(stk_cd)
        if not info_res["success"]:
            return f"종목 정보 조회 실패\n- 사유: {info_res['error_msg']}"
            
        data = info_res["data"]
        body = data.get("body", data)
        
        cur_prc_val = body.get("cur_prc")
        if not cur_prc_val:
            return "현재가 정보를 가져올 수 없습니다."
            
        try:
            cur_prc = int(str(cur_prc_val).strip().lstrip('+-'))
            if cur_prc <= 0:
                return f"현재가가 올바르지 않습니다: {cur_prc_val}"
        except ValueError:
            return f"현재가 파싱 오류: {cur_prc_val}"
            
        # 주문 수량 계산
        ord_qty = max_amount // cur_prc
        if ord_qty <= 0:
            return "지정한 금액이 현재가보다 작아 매수할 수 없습니다."
            
        # 매수 주문 수행
        res = buy_stock(stk_cd, ord_qty, 0)
        
        if not res["success"]:
            return f"주문 실패\n- 사유: {res['error_msg']}"
            
        order_data = res["data"]
        order_body = order_data.get("body", order_data)
        
        ord_no = order_body.get("ord_no", "")
        return_code = order_body.get("return_code")
        return_msg = order_body.get("return_msg", "")
        
        if return_code == 0:
            msg = (
                f"✅ 매수 주문 성공 (최대 금액 매수)\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"종목코드: {stk_cd}\n"
                f"최대 금액 설정값: {max_amount:,}원\n"
                f"계산된 수량: {ord_qty:,}주\n"
                f"주문수량: {ord_qty:,}주\n"
                f"주문단가: 시장가\n"
                f"주문번호: {ord_no}\n"
                f"메시지: {return_msg}\n"
                f"━━━━━━━━━━━━━━━━━━━"
            )
            return msg
        else:
            return f"주문 접수 오류: {return_msg} (코드: {return_code})"

    # 기존 수량 기준 매수 처리
    try:
        ord_qty = int(args[1].strip())
        if ord_qty <= 0:
            return "수량은 1 이상의 정수여야 합니다."
    except ValueError:
        return "수량은 정수로 입력해야 합니다."
        
    ord_pric = 0
    if len(args) >= 3:
        try:
            ord_pric = int(args[2].strip())
            if ord_pric < 0:
                return "지정가는 0 이상의 정수여야 합니다."
        except ValueError:
            return "지정가는 정수로 입력해야 합니다."
            
    res = buy_stock(stk_cd, ord_qty, ord_pric)
    
    if not res["success"]:
        return f"주문 실패\n- 사유: {res['error_msg']}"
        
    data = res["data"]
    body = data.get("body", data)
    
    ord_no = body.get("ord_no", "")
    return_code = body.get("return_code")
    return_msg = body.get("return_msg", "")
    
    if return_code == 0:
        prc_type = "지정가" if ord_pric > 0 else "시장가"
        prc_str = f"{ord_pric:,}원" if ord_pric > 0 else "시장가"
        msg = (
            f"✅ 매수 주문 성공\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"종목코드: {stk_cd}\n"
            f"주문수량: {ord_qty:,}주\n"
            f"주문단가: {prc_str} ({prc_type})\n"
            f"주문번호: {ord_no}\n"
            f"메시지: {return_msg}\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        return msg
    else:
        return f"주문 접수 오류: {return_msg} (코드: {return_code})"
