from api.stock import (
    get_trade_value_rank,
    get_fluctuation_rate_rank,
    get_trade_volume_rank,
    get_popular_search_rank
)
from utils.stock_code import clean_stock_code

def safe_int(val_str, default=0):
    if not val_str:
        return default
    try:
        # 부호와 쉼표 등을 지우고 정수로 변환
        cleaned = val_str.strip().replace("+", "").replace("-", "").replace(",", "")
        return int(cleaned)
    except ValueError:
        return default

def format_money(val_str):
    val = safe_int(val_str)
    return f"{val:,}원"

def format_qty(val_str):
    val = safe_int(val_str)
    if val >= 10000000:  # 1,000만 주 이상
        return f"{val/1000000:.1f}백만주"
    elif val >= 10000:   # 1만 주 이상
        return f"{val/10000:.1f}만주"
    else:
        return f"{val:,}주"

def format_trade_price(val_str):
    val = safe_int(val_str)
    # 단위: 백만원 -> 억원 환산
    billion_val = val / 100.0
    if billion_val >= 10000:
        trillion = int(billion_val // 10000)
        billion = billion_val % 10000
        return f"{trillion}조 {billion:,.0f}억"
    else:
        return f"{billion_val:,.1f}억"

def format_flu_rt_with_sig(sig, flu_rt_str):
    flu_rt = flu_rt_str.strip()
    # 기호 제거하고 양방향 통일
    val = flu_rt.replace("+", "").replace("-", "")
    
    if sig == "1":
        return f"🔥{val}%(상한)"
    elif sig == "2":
        return f"🔺{val}%"
    elif sig == "3" or val in ["0", "0.0", "0.00"]:
        return f"▫️{val}%"
    elif sig == "4":
        return f"❄️{val}%(하한)"
    elif sig == "5":
        return f"🔻{val}%"
    else:
        # 시그널이 없을 경우 문자열 자체 부호 판단
        if flu_rt.startswith("+"):
            return f"🔺{val}%"
        elif flu_rt.startswith("-"):
            return f"🔻{val}%"
        else:
            return f"{flu_rt}%"

def rank_command(args: list, chat_id: str = None) -> str:
    """
    'rank' 명령어를 처리합니다.
    사용법:
      - rank: 순위 메뉴 안내
      - rank {번호}: 번호에 해당하는 기준의 상위 20개 종목 리스트 출력
    """
    # 메뉴 안내 메시지
    menu_msg = (
        "📊 [시장 순위 조회 메뉴]\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "원하시는 순위의 번호를 입력해주세요.\n"
        "예: rank 2\n\n"
        "1. 거래대금 순위 (20위)\n"
        "2. 상승률 순위 (20위)\n"
        "3. 거래량 순위 (20위)\n"
        "4. 인기검색 순위 (20위)\n"
        "━━━━━━━━━━━━━━━━━━━"
    )

    if not args:
        return menu_msg

    choice = args[0].strip()
    if choice not in ["1", "2", "3", "4"]:
        return f"올바르지 않은 번호입니다.\n\n{menu_msg}"

    if choice == "1":
        # 1. 거래대금 상위
        res = get_trade_value_rank()
        if not res["success"]:
            return f"거래대금 순위 조회 실패\n- 사유: {res['error_msg']}"
        
        items = res["data"][:20]
        if not items:
            return "조회된 거래대금 순위 데이터가 없습니다."
            
        msg_lines = [
            "📊 거래대금 상위 20개 종목",
            "━━━━━━━━━━━━━━━━━━━"
        ]
        for item in items:
            rank = item.get("now_rank", "-")
            stk_nm = item.get("stk_nm", "")
            stk_cd = clean_stock_code(item.get("stk_cd", ""))
            cur_prc = format_money(item.get("cur_prc"))
            flu_rt = format_flu_rt_with_sig(item.get("pred_pre_sig"), item.get("flu_rt", "0"))
            trde_prica = format_trade_price(item.get("trde_prica"))
            
            msg_lines.append(
                f"{rank}위. {stk_nm} ({stk_cd})\n"
                f"    • 현재가: {cur_prc} ({flu_rt})\n"
                f"    • 거래대금: {trde_prica}"
            )
        msg_lines.append("━━━━━━━━━━━━━━━━━━━")
        return "\n".join(msg_lines)

    elif choice == "2":
        # 2. 상승률 상위
        res = get_fluctuation_rate_rank()
        if not res["success"]:
            return f"상승률 순위 조회 실패\n- 사유: {res['error_msg']}"
        
        items = res["data"][:20]
        if not items:
            return "조회된 상승률 순위 데이터가 없습니다."
            
        msg_lines = [
            "📈 상승률 상위 20개 종목",
            "━━━━━━━━━━━━━━━━━━━"
        ]
        for idx, item in enumerate(items, 1):
            stk_nm = item.get("stk_nm", "")
            stk_cd = clean_stock_code(item.get("stk_cd", ""))
            cur_prc = format_money(item.get("cur_prc"))
            flu_rt = format_flu_rt_with_sig(item.get("pred_pre_sig"), item.get("flu_rt", "0"))
            cntr_str = item.get("cntr_str", "0")
            
            msg_lines.append(
                f"{idx}위. {stk_nm} ({stk_cd})\n"
                f"    • 현재가: {cur_prc} ({flu_rt})\n"
                f"    • 체결강도: {cntr_str}%"
            )
        msg_lines.append("━━━━━━━━━━━━━━━━━━━")
        return "\n".join(msg_lines)

    elif choice == "3":
        # 3. 거래량 상위
        res = get_trade_volume_rank()
        if not res["success"]:
            return f"거래량 순위 조회 실패\n- 사유: {res['error_msg']}"
        
        items = res["data"][:20]
        if not items:
            return "조회된 거래량 순위 데이터가 없습니다."
            
        msg_lines = [
            "📊 당일 거래량 상위 20개 종목",
            "━━━━━━━━━━━━━━━━━━━"
        ]
        for idx, item in enumerate(items, 1):
            stk_nm = item.get("stk_nm", "")
            stk_cd = clean_stock_code(item.get("stk_cd", ""))
            cur_prc = format_money(item.get("cur_prc"))
            flu_rt = format_flu_rt_with_sig(item.get("pred_pre_sig"), item.get("flu_rt", "0"))
            trde_qty = format_qty(item.get("trde_qty"))
            
            msg_lines.append(
                f"{idx}위. {stk_nm} ({stk_cd})\n"
                f"    • 현재가: {cur_prc} ({flu_rt})\n"
                f"    • 거래량: {trde_qty}"
            )
        msg_lines.append("━━━━━━━━━━━━━━━━━━━")
        return "\n".join(msg_lines)

    elif choice == "4":
        # 4. 인기검색 순위
        res = get_popular_search_rank()
        if not res["success"]:
            return f"인기검색 순위 조회 실패\n- 사유: {res['error_msg']}"
        
        items = res["data"][:20]
        if not items:
            return "조회된 인기검색 순위 데이터가 없습니다."
            
        msg_lines = [
            "🔥 실시간 인기검색 상위 20개 종목",
            "━━━━━━━━━━━━━━━━━━━"
        ]
        for item in items:
            rank = item.get("bigd_rank", "-")
            stk_nm = item.get("stk_nm", "")
            stk_cd = clean_stock_code(item.get("stk_cd", ""))
            cur_prc = format_money(item.get("past_curr_prc"))
            flu_rt = format_flu_rt_with_sig(item.get("base_comp_sign"), item.get("base_comp_chgr", "0"))
            
            # 순위 변동 기호 처리
            chg_sign = item.get("rank_chg_sign", "")
            chg_val = item.get("rank_chg", "").strip().replace("+", "").replace("-", "")
            
            if chg_sign == "+":
                change = f"▲{chg_val}"
            elif chg_sign == "-":
                change = f"▼{chg_val}"
            else:
                change = "-"
                
            msg_lines.append(
                f"{rank}위. {stk_nm} ({stk_cd})\n"
                f"    • 현재가: {cur_prc} ({flu_rt})\n"
                f"    • 순위변동: {change}"
            )
        msg_lines.append("━━━━━━━━━━━━━━━━━━━")
        return "\n".join(msg_lines)
