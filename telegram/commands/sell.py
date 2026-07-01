from api.order import sell_stock
from api.stock import get_account_evaluation
from utils.stock_code import clean_stock_code

def sell_command(args: list, chat_id: str = None) -> str:
    """
    'sell' 명령어를 처리합니다.
    사용법:
    sell {종목코드|종목명} [수량]
    예: sell 삼성전자 10 (10주 매도)
    예: sell 삼성전자 (전량 매도)
    예: sell 005930 (전량 매도)
    """
    if len(args) < 1:
        return "사용법: sell {종목코드|종목명} [수량]\n예: sell 삼성전자 10\n예: sell 005930"
        
    if args[0].strip().lower() == "all":
        from api.session import session
        from api.stock import get_daily_balance_ratio
        from utils.blacklist import BlacklistManager
        
        eval_res = get_account_evaluation() if getattr(session, 'mode', 'real') == 'paper' else get_daily_balance_ratio()
        if not eval_res["success"]:
            return f"보유종목 조회를 실패했습니다.\n- 사유: {eval_res['error_msg']}"
            
        holdings = eval_res.get("holdings", [])
        active_holdings = [h for h in holdings if int(h.get("rmnd_qty", 0)) > 0]
        if not active_holdings:
            return "📁 현재 잔고에 보유 중인 종목이 없어 매도할 수 없습니다."
            
        success_list = []
        fail_list = []
        
        for h in active_holdings:
            stk_cd = clean_stock_code(h.get("stk_cd", ""))
            stk_nm = h.get("stk_nm", stk_cd)
            
            # 블랙리스트 검증
            if BlacklistManager().is_blacklisted(stk_cd):
                fail_list.append(f"- {stk_nm} ({stk_cd}): 매도 차단 (블랙리스트 종목)")
                continue
                
            qty = int(h.get("rmnd_qty", 0))
            
            # 매도 실행
            res = sell_stock(stk_cd, qty)
            if res["success"]:
                body = res["data"].get("body", res["data"])
                return_code = body.get("return_code")
                return_msg = body.get("return_msg", "")
                if return_code == 0:
                    success_list.append(f"- {stk_nm} ({stk_cd}): {qty:,}주")
                else:
                    fail_list.append(f"- {stk_nm} ({stk_cd}): {return_msg} (코드: {return_code})")
            else:
                fail_list.append(f"- {stk_nm} ({stk_cd}): {res.get('error_msg')}")
                
        msg_lines = ["🔔 [보유 종목 전량 매도 결과]"]
        if success_list:
            msg_lines.append("\n✅ 매도 성공 종목:")
            msg_lines.extend(success_list)
        if fail_list:
            msg_lines.append("\n❌ 매도 실패/차단 종목:")
            msg_lines.extend(fail_list)
            
        return "\n".join(msg_lines)

    stk_input = clean_stock_code(args[0].strip())
    
    # 블랙리스트 사전 검사 (6자리 코드인 경우)
    if len(stk_input) == 6 and stk_input.isdigit():
        from utils.blacklist import BlacklistManager
        if BlacklistManager().is_blacklisted(stk_input):
            return f"❌ 블랙리스트 제한: 이 종목({stk_input})은 블랙리스트에 등록되어 있어 매도할 수 없습니다."
    
    # 보유종목 조회
    eval_res = get_account_evaluation()
    if not eval_res["success"]:
        return f"보유종목 조회를 실패했습니다.\n- 사유: {eval_res['error_msg']}"
        
    holdings = eval_res.get("holdings", [])
    
    # 보유 종목 중 입력값과 일치하는 항목 검색 (종목코드 또는 종목명 비교)
    matched_holding = None
    for h in holdings:
        h_stk_cd = clean_stock_code(h.get("stk_cd", ""))
        h_stk_nm = h.get("stk_nm", "")
        if stk_input == h_stk_cd or stk_input == h_stk_nm:
            matched_holding = h
            break

    stk_cd = None
    stk_nm = stk_input
    ord_qty = None

    # 수량 결정
    if len(args) >= 2:
        # 수량이 입력된 경우
        try:
            ord_qty = int(args[1].strip())
            if ord_qty <= 0:
                return "수량은 1 이상의 정수여야 합니다."
        except ValueError:
            return "수량은 정수로 입력해야 합니다."
            
        if matched_holding:
            stk_cd = clean_stock_code(matched_holding.get("stk_cd", ""))
            stk_nm = matched_holding.get("stk_nm", stk_input)
        else:
            # 보유종목에 없더라도 입력한 값이 6자리 종목코드 형식이면 매도 시도
            if len(stk_input) == 6 and stk_input.isdigit():
                stk_cd = stk_input
            else:
                return f"보유종목 중 '{stk_input}'을(를) 찾을 수 없습니다. 정확한 종목명 또는 6자리 종목코드를 입력해주세요."
    else:
        # 수량이 입력되지 않은 경우 (전량 매도)
        if not matched_holding:
            return f"❌ 보유종목 중 '{stk_input}'을(를) 찾을 수 없어 전량 매도할 수 없습니다."
            
        stk_cd = clean_stock_code(matched_holding.get("stk_cd", ""))
        stk_nm = matched_holding.get("stk_nm", stk_input)
        
        try:
            ord_qty = int(matched_holding.get("rmnd_qty", 0))
        except (ValueError, TypeError):
            ord_qty = 0
            
        if ord_qty <= 0:
            return f"❌ '{stk_nm}'의 보유 수량이 0주이므로 매도할 수 없습니다."

    # 블랙리스트 검사
    from utils.blacklist import BlacklistManager
    if BlacklistManager().is_blacklisted(stk_cd):
        return f"❌ 블랙리스트 제한: 이 종목({stk_cd})은 블랙리스트에 등록되어 있어 매도할 수 없습니다."

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
            f"주문수량: {ord_qty:,}주 (전량 매도)\n" if len(args) < 2 else f"주문수량: {ord_qty:,}주\n"
        )
        msg += (
            f"주문단가: 시장가\n"
            f"주문번호: {ord_no}\n"
            f"메시지: {return_msg}\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        return msg
    else:
        return f"매도 주문 접수 오류: {return_msg} (코드: {return_code})"
