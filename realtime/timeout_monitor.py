import time
import logging
import threading
from api.stock import get_unfilled_orders, get_stock_basic_info
from api.order import cancel_order, buy_stock
from utils.settings import get_setting
from utils.market import get_price_up_by_ticks

logger = logging.getLogger(__name__)

def monitor_order_timeout(stk_cd, ord_no, qty, ord_pric, timeout, action):
    logger.info(f"[TimeoutMonitor] 주문 감시 시작: 주문번호 #{ord_no}, 종목={stk_cd}, 대기시간={timeout}초, 액션={action}")
    
    # 1. 매수 주문 직후 미체결 상태 확인
    # 만약 주문 직후에 이미 미체결 목록에 없다면 이미 체결 완료된 것이므로 종료
    time.sleep(0.5)  # API 반영 속도를 고려하여 0.5초 대기
    init_res = get_unfilled_orders()
    if init_res["success"]:
        init_orders = init_res["orders"]
        is_still_unfilled = any(o["ord_no"] == ord_no for o in init_orders)
        if not is_still_unfilled:
            logger.info(f"[TimeoutMonitor] 주문 #{ord_no}가 즉시 체결 완료되어 감시를 종료합니다.")
            return
            
    # 2. s초 동안 대기 (0.5초 선대기 차감)
    time.sleep(max(0, timeout - 0.5))
    
    # 3. s초 지난 후 미체결 목록 조회하여 상태 재확인
    res = get_unfilled_orders()
    if not res["success"]:
        logger.error(f"[TimeoutMonitor] 미체결 조회 실패: {res['error_msg']}")
        return
        
    orders = res["orders"]
    target_order = None
    for o in orders:
        if o["ord_no"] == ord_no:
            target_order = o
            break
            
    if not target_order:
        logger.info(f"[TimeoutMonitor] 주문 #{ord_no}가 대기 시간 내에 체결 완료되었거나 취소되었습니다.")
        return
        
    # 아직 미체결된 상태이므로 액션 실행
    from telegram.bot import reply_message
    from config.config import telegram_chat_id
    
    if action == "cancel":
        logger.info(f"[TimeoutMonitor] 주문 #{ord_no} 미체결로 인한 자동 취소 실행")
        c_res = cancel_order(stk_cd, ord_no, cncl_qty=0)
        if c_res["success"]:
            msg = (
                f"⏱️ [미체결 주문 자동 취소]\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🏢 종목: {target_order['stk_nm']} ({stk_cd})\n"
                f"주문번호: #{ord_no}\n"
                f"사유: {timeout}초간 미체결로 인한 자동 취소 완료\n"
                f"━━━━━━━━━━━━━━━━━━━"
            )
            reply_message(telegram_chat_id, msg)
        else:
            msg = f"⚠️ [미체결 주문 자동 취소 실패]\n- 종목: {target_order['stk_nm']}\n- 주문번호: #{ord_no}\n- 오류: {c_res['error_msg']}"
            reply_message(telegram_chat_id, msg)
            
    elif action == "market":
        logger.info(f"[TimeoutMonitor] 주문 #{ord_no} 미체결로 인한 호가 상향 재주문 실행")
        
        # 1) 기존 주문 취소
        c_res = cancel_order(stk_cd, ord_no, cncl_qty=0)
        if not c_res["success"]:
            logger.error(f"[TimeoutMonitor] 기존 주문 #{ord_no} 취소 실패: {c_res['error_msg']}")
            return
            
        # 2) 현재가 조회
        info_res = get_stock_basic_info(stk_cd)
        cur_prc = 0
        if info_res["success"]:
            body = info_res["data"].get("body", info_res["data"])
            cur_prc_val = body.get("cur_prc")
            if cur_prc_val:
                try:
                    cur_prc = int(str(cur_prc_val).strip().lstrip('+-'))
                except ValueError:
                    pass
                    
        # 3) 1틱 올린 지정가 계산
        next_pric = get_price_up_by_ticks(ord_pric, 1)
        tick_diff = next_pric - ord_pric
        
        # 4) 시장가 주문 전환 조건 체크 (다음 호가가 현재가 이상이거나 현재가를 알 수 없는 경우)
        if cur_prc > 0 and next_pric >= cur_prc:
            logger.info(f"[TimeoutMonitor] 목표 호가({next_pric}원)가 현재가({cur_prc}원) 이상이므로 시장가 주문 실행")
            b_res = buy_stock(stk_cd, target_order["ord_remnq"], ord_pric=0)
            if b_res["success"]:
                b_body = b_res["data"].get("body", b_res["data"])
                new_ord_no = b_body.get("ord_no", "")
                msg = (
                    f"⏱️ [미체결 주문 -> 시장가 전환 완료]\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"🏢 종목: {target_order['stk_nm']} ({stk_cd})\n"
                    f"기존 주문번호: #{ord_no} ({ord_pric:,}원)\n"
                    f"신규 주문번호: #{new_ord_no} (시장가 / 단가 0원 매수 접수)\n"
                    f"사유: 호가 상향 중 현재가({cur_prc:,}원) 도달로 시장가(단가 0) 전환\n"
                    f"━━━━━━━━━━━━━━━━━━━"
                )
                reply_message(telegram_chat_id, msg)
            else:
                msg = f"⚠️ [시장가 재주문 실패]\n- 종목: {target_order['stk_nm']}\n- 오류: {b_res['error_msg']}"
                reply_message(telegram_chat_id, msg)
        else:
            # 1틱 상향 지정가 재주문 실행
            b_res = buy_stock(stk_cd, target_order["ord_remnq"], ord_pric=next_pric)
            if b_res["success"]:
                b_body = b_res["data"].get("body", b_res["data"])
                new_ord_no = b_body.get("ord_no", "")
                msg = (
                    f"⏱️ [미체결 주문 -> 호가 상향 재주문]\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"🏢 종목: {target_order['stk_nm']} ({stk_cd})\n"
                    f"기존 주문번호: #{ord_no} ({ord_pric:,}원)\n"
                    f"신규 주문번호: #{new_ord_no} ({next_pric:,}원)\n"
                    f"사유: {timeout}초간 미체결로 1틱 상향(+{tick_diff:,}원) 재주문 실행\n"
                    f"━━━━━━━━━━━━━━━━━━━"
                )
                reply_message(telegram_chat_id, msg)
                
                # 새 주문에 대해 다시 모니터링 수행 (재귀)
                start_timeout_monitor(stk_cd, new_ord_no, target_order["ord_remnq"], next_pric)
            else:
                msg = f"⚠️ [호가 상향 재주문 실패]\n- 종목: {target_order['stk_nm']}\n- 오류: {b_res['error_msg']}"
                reply_message(telegram_chat_id, msg)


def start_timeout_monitor(stk_cd, ord_no, qty, ord_pric):
    """
    주문 만료 설정이 활성화되어 있고 지정가 주문인 경우 백그라운드 모니터링 스레드를 시작합니다.
    """
    try:
        timeout = int(get_setting("order_timeout_seconds", 0))
    except (ValueError, TypeError):
        timeout = 0
        
    action = get_setting("order_timeout_action", "cancel")
    
    if timeout <= 0 or ord_pric <= 0:
        return
        
    threading.Thread(
        target=monitor_order_timeout,
        args=(stk_cd, ord_no, qty, ord_pric, timeout, action),
        daemon=True
    ).start()
