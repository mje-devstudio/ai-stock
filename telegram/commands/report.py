from api.stock import get_account_evaluation
from utils.stock_code import clean_stock_code

def report_command(args: list, chat_id: str = None) -> str:
    """
    'report' 또는 'r' 명령어를 처리하여 사용자의 자금현황과 보유 종목 목록을 반환합니다.
    """
    res = get_account_evaluation()
    if not res["success"]:
        return f"자금 현황 조회 실패\n- 사유: {res['error_msg']}"
        
    account_info = res["account_info"]
    holdings = res["holdings"]
    
    def parse_int(val_str, default=0):
        if not val_str:
            return default
        try:
            return int(val_str)
        except ValueError:
            return default

    def parse_float(val_str, default=0.0):
        if not val_str:
            return default
        try:
            return float(val_str)
        except ValueError:
            return default

    def format_money(val_str):
        val = parse_int(val_str, 0)
        return f"{val:,}원"

    def format_qty(val_str):
        val = parse_int(val_str, 0)
        return f"{val:,}주"

    def format_ratio(val_str):
        val = parse_float(val_str, 0.0)
        return f"{val:.2f}%"

    acnt_nm = account_info.get("acnt_nm") or "-"
    brch_nm = account_info.get("brch_nm") or "-"
    
    entr = format_money(account_info.get("entr"))
    d2_entra = format_money(account_info.get("d2_entra"))
    tot_est_amt = format_money(account_info.get("tot_est_amt"))
    aset_evlt_amt = format_money(account_info.get("aset_evlt_amt"))
    tot_pur_amt = format_money(account_info.get("tot_pur_amt"))
    
    lspft = format_money(account_info.get("lspft"))
    lspft_rt = format_ratio(account_info.get("lspft_rt"))
    
    tdy_lspft = format_money(account_info.get("tdy_lspft"))
    tdy_lspft_rt = format_ratio(account_info.get("tdy_lspft_rt"))
    
    # 누적/당일 손익의 부호에 따른 기호 설정
    lspft_val = parse_int(account_info.get("lspft"), 0)
    lspft_sign = "+" if lspft_val > 0 else ""
    
    tdy_lspft_val = parse_int(account_info.get("tdy_lspft"), 0)
    tdy_sign = "+" if tdy_lspft_val > 0 else ""

    msg_lines = [
        "📋 자금 및 보유종목 현황",
        "━━━━━━━━━━━━━━━━━━━",
        f"계좌명: {acnt_nm}",
        f"지점명: {brch_nm}",
        "",
        "💰 [자금 현황]",
        f"• 예수금: {entr}",
        f"• D+2추정예수금: {d2_entra}",
        f"• 예탁자산평가액: {aset_evlt_amt}",
        f"• 유가잔고평가액: {tot_est_amt}",
        f"• 총매입금액: {tot_pur_amt}",
        f"• 누적투자손익: {lspft_sign}{lspft} ({lspft_sign}{lspft_rt})",
        f"• 당일투자손익: {tdy_sign}{tdy_lspft} ({tdy_sign}{tdy_lspft_rt})",
        ""
    ]
    
    msg_lines.append(f"📈 [보유 종목] ({len(holdings)}개)")
    
    if not holdings:
        msg_lines.append("보유 중인 종목이 없습니다.")
    else:
        for idx, item in enumerate(holdings, 1):
            stk_cd = item.get("stk_cd", "")
            short_cd = clean_stock_code(stk_cd)
                
            stk_nm = item.get("stk_nm", "")
            rmnd_qty = format_qty(item.get("rmnd_qty"))
            avg_prc = format_money(item.get("avg_prc"))
            cur_prc = format_money(item.get("cur_prc"))
            evlt_amt = format_money(item.get("evlt_amt"))
            pl_amt = format_money(item.get("pl_amt"))
            pl_rt = format_ratio(item.get("pl_rt"))
            
            # 부호에 따른 기호 추가 (+/-)
            pl_val = parse_int(item.get("pl_amt"), 0)
            pl_sign = "+" if pl_val > 0 else ""
            
            msg_lines.append(
                f"{idx}. {stk_nm} ({short_cd})\n"
                f"   • 보유수량: {rmnd_qty}\n"
                f"   • 평균단가: {avg_prc} / 현재가: {cur_prc}\n"
                f"   • 평가금액: {evlt_amt}\n"
                f"   • 평가손익: {pl_sign}{pl_amt} ({pl_sign}{pl_rt})"
            )
            
    msg_lines.append("━━━━━━━━━━━━━━━━━━━")
    
    return "\n".join(msg_lines)
