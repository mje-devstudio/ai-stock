from api.order import buy_stock
from api.stock import get_stock_basic_info
from utils.stock_code import clean_stock_code
from utils.market import get_price_down_by_ticks

def buy_command(args: list, chat_id: str = None) -> str:
    """
    'buy' 명령어를 처리합니다.
    사용법: 
    buy {종목코드} {수량} : 시장가 매수
    buy {종목코드} {수량} {지정가} : 지정가 매수
    buy {종목코드} max {금액} : 최대 금액 기준 시장가 매수
    buy {종목코드} {수량} max {금액} : 지정 수량 한도로 최대 금액 매수
    buy {종목코드} {수량} tick {틱} : 호가를 {틱}만큼 낮춰 지정가 매수
    buy {종목코드} max {금액} tick {틱} : 호가를 {틱}만큼 낮춘 지정가 기준으로 최대 금액 매수
    buy {종목코드} {수량} max {금액} tick {틱} : 호가를 {틱}만큼 낮춘 지정가 기준으로 지정 수량 한도로 최대 금액 매수
    
    예: buy 005930 10 (삼성전자 10주 시장가 매수)
    예: buy 005930 10 80000 (삼성전자 10주 80,000원 지정가 매수)
    예: buy 005930 max 500000 (삼성전자 50만원 한도 내 최대 매수)
    예: buy 005930 10 max 500000 (삼성전자 최대 10주 또는 50만원 한도 매수)
    예: buy 005930 10 tick 2 (삼성전자 10주 현재가보다 2틱 아래 지정가 매수)
    예: buy 005930 10 max 500000 tick 2 (2틱 아래 가격으로 최대 10주 또는 50만원 한도 매수)
    """
    if len(args) < 2:
        return "사용법:\n- 수량 기준: buy {종목코드} {수량} [지정가]\n- 금액 기준: buy {종목코드} max {금액}\n- 수량/금액 혼합: buy {종목코드} {수량} max {금액}\n- 틱 옵션: 기존 명령어 뒤에 'tick {틱}' 추가"
    
    # 1. tick 파라미터 파싱
    tick = 0
    tick_index = -1
    for i, arg in enumerate(args):
        if arg.strip().lower() == "tick":
            tick_index = i
            break
            
    if tick_index != -1:
        if tick_index == len(args) - 1:
            return "틱 값을 입력해주세요. (예: tick 2)"
        try:
            tick = int(args[tick_index + 1].strip())
            if tick <= 0:
                return "틱 값은 1 이상의 정수여야 합니다."
        except ValueError:
            return "틱 값은 정수로 입력해야 합니다."
        
        # tick 키워드와 값 제거
        args = args[:tick_index] + args[tick_index + 2:]
        
    if len(args) < 2:
        return "사용법:\n- 수량 기준: buy {종목코드} {수량} [지정가]\n- 금액 기준: buy {종목코드} max {금액}\n- 수량/금액 혼합: buy {종목코드} {수량} max {금액}\n- 틱 옵션: 기존 명령어 뒤에 'tick {틱}' 추가"

    stk_cd = clean_stock_code(args[0].strip())
    if len(stk_cd) != 6 or not stk_cd.isdigit():
        return "종목코드는 6자리 숫자여야 합니다. (예: 005930)"

    # 2. 인수 개수와 형식에 따른 케이스 분석
    is_max_mode = False
    max_amount = 0
    ord_qty = None
    ord_pric = 0

    # Case D: buy {종목코드} {수량} max {금액}
    if len(args) >= 4 and args[2].strip().lower() == "max":
        is_max_mode = True
        try:
            ord_qty = int(args[1].strip())
            if ord_qty <= 0:
                return "수량은 1 이상의 정수여야 합니다."
        except ValueError:
            return "수량은 정수로 입력해야 합니다."
            
        try:
            max_amount = int(args[3].strip())
            if max_amount <= 0:
                return "최대 금액은 1 이상의 정수여야 합니다."
        except ValueError:
            return "최대 금액은 정수로 입력해야 합니다."

    # Case C: buy {종목코드} max {금액}
    elif len(args) >= 3 and args[1].strip().lower() == "max":
        is_max_mode = True
        try:
            max_amount = int(args[2].strip())
            if max_amount <= 0:
                return "최대 금액은 1 이상의 정수여야 합니다."
        except ValueError:
            return "최대 금액은 정수로 입력해야 합니다."

    # Case B: buy {종목코드} {수량} {지정가}
    elif len(args) >= 3:
        try:
            ord_qty = int(args[1].strip())
            if ord_qty <= 0:
                return "수량은 1 이상의 정수여야 합니다."
        except ValueError:
            return "수량은 정수로 입력해야 합니다."
            
        try:
            ord_pric = int(args[2].strip())
            if ord_pric < 0:
                return "지정가는 0 이상의 정수여야 합니다."
        except ValueError:
            return "지정가는 정수로 입력해야 합니다."
            
        if tick > 0:
            return "지정가 매수 주문에는 tick 옵션을 사용할 수 없습니다. 시장가 매수(수량 기준 또는 금액 기준)에만 적용 가능합니다."

    # Case A: buy {종목코드} {수량}
    else:
        try:
            ord_qty = int(args[1].strip())
            if ord_qty <= 0:
                return "수량은 1 이상의 정수여야 합니다."
        except ValueError:
            return "수량은 정수로 입력해야 합니다."

    # 3. 비즈니스 로직 실행
    if is_max_mode:
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
            
        # 상한가 / 하한가 정보 파싱 및 검증
        upl_pric_val = body.get("upl_pric")
        lst_pric_val = body.get("lst_pric")
        upl_pric, lst_pric = 0, 0
        try:
            if upl_pric_val:
                upl_pric = int(str(upl_pric_val).strip().lstrip('+-'))
            if lst_pric_val:
                lst_pric = int(str(lst_pric_val).strip().lstrip('+-'))
        except ValueError:
            pass

        # 주문 가격 결정
        if tick > 0:
            ord_pric = get_price_down_by_ticks(cur_prc, tick)
            if ord_pric <= 0:
                return f"현재가 {cur_prc:,}원에서 {tick}틱을 낮춘 가격이 0원 이하입니다."
                
            # 상하한가 범위 검증
            if lst_pric > 0 and ord_pric < lst_pric:
                return f"계산된 지정가({ord_pric:,}원)가 하한가({lst_pric:,}원)보다 낮습니다. 주문을 진행할 수 없습니다."
            if upl_pric > 0 and ord_pric > upl_pric:
                return f"계산된 지정가({ord_pric:,}원)가 상한가({upl_pric:,}원)보다 높습니다. 주문을 진행할 수 없습니다."
        else:
            ord_pric = 0

        # 주문 수량 계산 (지정가가 있으면 지정가 기준, 없으면 현재가 기준)
        price_for_calc = ord_pric if ord_pric > 0 else cur_prc
        max_possible_qty = max_amount // price_for_calc
        
        if ord_qty is not None:
            # Case D: 지정된 수량과 금액 기준의 한도 수량 중 최솟값 적용
            final_qty = min(ord_qty, max_possible_qty)
        else:
            # Case C: 금액 기준 한도 수량 전체 적용
            final_qty = max_possible_qty
            
        if final_qty <= 0:
            if ord_qty is not None and ord_qty > max_possible_qty:
                return f"지정한 금액({max_amount:,}원)으로 계산된 최대 수량({max_possible_qty:,}주)이 0주입니다. 매수할 수 없습니다."
            else:
                return "지정한 금액이 현재가보다 작아 매수할 수 없습니다."
            
        # 매수 주문 수행
        res = buy_stock(stk_cd, final_qty, ord_pric)
        
        if not res["success"]:
            return f"주문 실패\n- 사유: {res['error_msg']}"
            
        order_data = res["data"]
        order_body = order_data.get("body", order_data)
        
        ord_no = order_body.get("ord_no", "")
        return_code = order_body.get("return_code")
        return_msg = order_body.get("return_msg", "")
        
        if return_code == 0:
            from realtime.timeout_monitor import start_timeout_monitor
            start_timeout_monitor(stk_cd, ord_no, final_qty, ord_pric)
            prc_str = f"{ord_pric:,}원 (지정가, {tick}틱 아래)" if tick > 0 else "시장가"
            limit_info = ""
            if ord_qty is not None:
                limit_info = f"요청 제한 수량: {ord_qty:,}주\n"
            msg = (
                f"✅ 매수 주문 성공 (최대 금액 매수)\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"종목코드: {stk_cd}\n"
                f"최대 금액 설정값: {max_amount:,}원\n"
                f"{limit_info}"
                f"계산된 수량: {final_qty:,}주\n"
                f"주문수량: {final_qty:,}주\n"
                f"주문단가: {prc_str}\n"
                f"주문번호: {ord_no}\n"
                f"메시지: {return_msg}\n"
                f"━━━━━━━━━━━━━━━━━━━"
            )
            return msg
        else:
            return f"주문 접수 오류: {return_msg} (코드: {return_code})"

    else:
        # Case A: 수량 기준 주문 (tick에 따라 지정가 또는 시장가)
        if tick > 0:
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
                
            # 상한가 / 하한가 정보 파싱 및 검증
            upl_pric_val = body.get("upl_pric")
            lst_pric_val = body.get("lst_pric")
            upl_pric, lst_pric = 0, 0
            try:
                if upl_pric_val:
                    upl_pric = int(str(upl_pric_val).strip().lstrip('+-'))
                if lst_pric_val:
                    lst_pric = int(str(lst_pric_val).strip().lstrip('+-'))
            except ValueError:
                pass

            ord_pric = get_price_down_by_ticks(cur_prc, tick)
            if ord_pric <= 0:
                return f"현재가 {cur_prc:,}원에서 {tick}틱을 낮춘 가격이 0원 이하입니다."
                
            # 상하한가 범위 검증
            if lst_pric > 0 and ord_pric < lst_pric:
                return f"계산된 지정가({ord_pric:,}원)가 하한가({lst_pric:,}원)보다 낮습니다. 주문을 진행할 수 없습니다."
            if upl_pric > 0 and ord_pric > upl_pric:
                return f"계산된 지정가({ord_pric:,}원)가 상한가({upl_pric:,}원)보다 높습니다. 주문을 진행할 수 없습니다."
            
        res = buy_stock(stk_cd, ord_qty, ord_pric)
        
        if not res["success"]:
            return f"주문 실패\n- 사유: {res['error_msg']}"
            
        data = res["data"]
        body = data.get("body", data)
        
        ord_no = body.get("ord_no", "")
        return_code = body.get("return_code")
        return_msg = body.get("return_msg", "")
        
        if return_code == 0:
            from realtime.timeout_monitor import start_timeout_monitor
            start_timeout_monitor(stk_cd, ord_no, ord_qty, ord_pric)
            if tick > 0:
                prc_type = "지정가"
                prc_str = f"{ord_pric:,}원 ({tick}틱 아래)"
            else:
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



