from api.stock import get_unfilled_orders
from api.order import cancel_order

def ccl_command(args: list, chat_id: str = None) -> str:
    """
    'ccl' 명령어를 처리하여 미체결 주문을 일괄 취소하거나 부분 취소합니다.
    
    사용법:
    1. ccl pend : 현재 모든 미체결 주문을 일괄 취소합니다.
    2. ccl {주문번호} [취소수량] : 특정 주문을 취소합니다. 취소수량 생략 시 잔량 전량 취소합니다.
    3. ccl {종목코드/종목명} : 특정 종목의 모든 미체결 주문을 취소합니다.
    """
    if not args:
        return (
            "사용법:\n"
            "• ccl pend : 모든 미체결 주문 일괄 취소\n"
            "• ccl {주문번호} [취소수량] : 특정 주문 취소 (수량 생략 시 전량 취소)\n"
            "• ccl {종목코드/종목명} : 특정 종목의 모든 미체결 주문 취소"
        )
        
    target = args[0].strip()
    target_lower = target.lower()
    
    # 1. 미체결 주문 목록 조회
    orders_res = get_unfilled_orders()
    if not orders_res["success"]:
        return f"미체결 주문 조회 실패\n- 사유: {orders_res['error_msg']}"
        
    unfilled_orders = orders_res["orders"]
    if not unfilled_orders:
        return "취소할 미체결 주문이 없습니다."
        
    # 취소 대상 주문 선별
    targets_to_cancel = []
    cancel_qty = 0  # 0 이면 전량 취소
    
    if target_lower == "pend":
        # 1) 전체 취소
        targets_to_cancel = unfilled_orders
    else:
        # 2) 주문번호 또는 종목 식별
        # 두 번째 인자로 취소 수량이 왔는지 체크
        if len(args) > 1:
            try:
                cancel_qty = int(args[1])
                if cancel_qty < 0:
                    return "취소수량은 0 이상의 정수여야 합니다."
            except ValueError:
                return f"취소수량이 올바르지 않습니다: {args[1]}"
                
        # 접두어 '#'가 붙어있는 경우 주문번호로 확정 판정
        is_order_no_query = target.startswith("#")
        clean_target = target.lstrip("#").strip()
        
        # 정수 변환 시도 (주문번호 매칭 및 단축 입력 대응용)
        target_int = None
        if clean_target.isdigit():
            target_int = int(clean_target)
            
        # 매칭 필터링
        for order in unfilled_orders:
            ord_no_str = order["ord_no"]
            ord_no_int = None
            try:
                ord_no_int = int(ord_no_str)
            except ValueError:
                pass
                
            stk_cd_str = order["stk_cd"]
            
            if is_order_no_query:
                # A. '#주문번호' 형태로 명시된 경우 -> 주문번호 매칭만 수행 (단축번호 및 완전번호 매치)
                if target_int is not None and ord_no_int == target_int:
                    targets_to_cancel.append(order)
                    break
                elif ord_no_str == clean_target:
                    targets_to_cancel.append(order)
                    break
            else:
                # B. 접두어가 없는 경우 -> 종목코드, 종목명, 혹은 7자리 주문번호 완전 매칭
                # B-1. 종목코드 완전 매칭
                if stk_cd_str == clean_target:
                    targets_to_cancel.append(order)
                # B-2. 종목명 매칭 (대소문자/공백 제거 비교)
                elif order["stk_nm"].replace(" ", "").lower() == clean_target.replace(" ", "").lower():
                    targets_to_cancel.append(order)
                # B-3. 7자리 주문번호 완전 매칭 (입력값이 7자리 숫자이고 주문번호와 일치하는 경우)
                elif len(clean_target) == 7 and ord_no_str == clean_target:
                    targets_to_cancel.append(order)
                    break

    if not targets_to_cancel:
        return f"입력한 대상('{target}')과 일치하는 미체결 주문을 찾을 수 없습니다."
        
    # 수량 부분 취소 제약 조건 체크
    if cancel_qty > 0 and len(targets_to_cancel) > 1:
        return "여러 주문에 대한 동시 수량 부분 취소는 지원하지 않습니다. 하나의 주문번호를 지정해주세요."
        
    # 취소 실행
    success_count = 0
    fail_count = 0
    fail_details = []
    
    for order in targets_to_cancel:
        stk_cd = order["stk_cd"]
        stk_nm = order["stk_nm"]
        ord_no = order["ord_no"]
        
        res = cancel_order(stk_cd=stk_cd, orig_ord_no=ord_no, cncl_qty=cancel_qty)
        
        if res["success"]:
            res_data = res["data"]
            res_body = res_data.get("body", res_data)
            return_code = res_body.get("return_code")
            return_msg = res_body.get("return_msg", "")
            
            if return_code == 0:
                success_count += 1
            else:
                fail_count += 1
                fail_details.append(f"{stk_nm}({ord_no}): {return_msg} (코드: {return_code})")
        else:
            fail_count += 1
            fail_details.append(f"{stk_nm}({ord_no}): {res['error_msg']}")
            
    # 결과 메시지 작성
    msg_lines = [
        "🚫 미체결 주문 취소 결과",
        "━━━━━━━━━━━━━━━━━━━",
        f"대상 주문 수: {len(targets_to_cancel)}건",
        f"성공: {success_count}건",
        f"실패: {fail_count}건"
    ]
    
    if cancel_qty > 0:
        msg_lines.append(f"취소 요청 수량: {cancel_qty}주 (부분취소)")
        
    if fail_count > 0:
        msg_lines.append("")
        msg_lines.append("⚠️ [실패 상세 사유]")
        for detail in fail_details:
            msg_lines.append(f"• {detail}")
            
    msg_lines.append("━━━━━━━━━━━━━━━━━━━")
    
    return "\n".join(msg_lines)
