from utils.settings import set_setting, get_setting

def ddcrs_command(args: list, chat_id: str = None) -> str:
    """데드크로스를 위한 분봉 설정 및 감시 상태 관리 명령어입니다.
    
    사용법:
      1. 분봉 값 설정:
         ddcrs intv {단기} {장기} (예: ddcrs intv 5 20)
         ddcrs {단기} {장기} (예: ddcrs 5 20)
      2. 감시 상태 및 보유종목 조회:
         ddcrs list
         ddcrs status
      3. 실시간 데드크로스 감시 시작/중지: ddcrs start / ddcrs stop
    """
    if not args:
        return (
            "사용법:\n"
            "• 분봉 값 설정: ddcrs intv {단기} {장기} (또는 ddcrs {단기} {장기})\n"
            "• 감시 상태 조회: ddcrs list (또는 ddcrs status)\n"
            "• 감시 시작: ddcrs start\n"
            "• 감시 중단: ddcrs stop"
        )
        
    subcmd = args[0].strip().lower()
    
    # 1. 감시 상태 및 종목 조회 (list / status)
    if subcmd in ("list", "status"):
        from realtime.ddcrs_runner import DDCRSManager
        manager = DDCRSManager()
        
        status_str = "✅ 실시간 데드크로스 감시가 실행 중입니다." if manager.active else "🛑 데드크로스 감시가 비활성화 상태입니다."
        short_val = manager.short_period if manager.active else int(get_setting("ddcrs_short", 5))
        long_val = manager.long_period if manager.active else int(get_setting("ddcrs_long", 20))
        
        msg_lines = [
            "💀 데드크로스 감시 상태",
            "━━━━━━━━━━━━━━━━━━━",
            status_str,
            f"• 설정: {short_val}분선 / {long_val}분선",
            "━━━━━━━━━━━━━━━━━━━",
            "📈 실시간 감시 중인 보유종목:"
        ]
        
        if not manager.active:
            msg_lines.append("- 감시가 정지된 상태입니다. start ddcrs 명령어로 기동하세요.")
        elif not manager.tracked_stocks:
            msg_lines.append("- 현재 감시 중인 보유 종목이 없습니다.")
        else:
            for stk_cd, info in manager.tracked_stocks.items():
                qty = info.get("qty", 0)
                buy_uv = info.get("buy_uv", 0.0)
                is_selling = info.get("is_selling", False)
                selling_status = " (매도 진행 중)" if is_selling else ""
                
                # 현재 MA 정보 계산
                candles = manager.candles_history.get(stk_cd, [])
                ma_info = ""
                if len(candles) >= long_val:
                    curr_short_ma = manager._calculate_ma(candles, short_val)
                    curr_long_ma = manager._calculate_ma(candles, long_val)
                    if curr_short_ma is not None and curr_long_ma is not None:
                        ma_info = f" | MA({short_val}/{long_val}): {curr_short_ma:.1f}/{curr_long_ma:.1f}"
                        
                msg_lines.append(f"- {stk_cd} | {qty:,}주 (평단: {buy_uv:,}원){ma_info}{selling_status}")
                
        msg_lines.append("━━━━━━━━━━━━━━━━━━━")
        return "\n".join(msg_lines)
        
    # 2. 분봉 값 설정 (intv 혹은 숫자 기입 분기)
    elif subcmd == "intv":
        if len(args) < 3:
            return "사용법: ddcrs intv {단기} {장기}\n예: ddcrs intv 5 20"
        short_str = args[1].strip()
        long_str = args[2].strip()
        return _set_intervals(short_str, long_str)
        
    elif subcmd == "start":
        from realtime.ddcrs_runner import DDCRSManager
        manager = DDCRSManager()
        res = manager.start(chat_id)
        return res if res else "✅ 데드크로스 감시가 실행되었습니다."

    elif subcmd == "stop":
        from realtime.ddcrs_runner import DDCRSManager
        manager = DDCRSManager()
        return manager.stop()

    elif not subcmd.isdigit():
        return (
            "올바르지 않은 명령 또는 인수 유형입니다.\n"
            "사용법:\n"
            "• 분봉 값 설정: ddcrs intv {단기} {장기} (또는 ddcrs {단기} {장기})\n"
            "• 감시 상태 조회: ddcrs list\n"
            "• 감시 시작: ddcrs start\n"
            "• 감시 중단: ddcrs stop"
        )
        
    else:
        # ddcrs {단기} {장기} 형식 처리
        if len(args) < 2:
            return "사용법: ddcrs {단기} {장기}\n예: ddcrs 5 20"
        short_str = args[0].strip()
        long_str = args[1].strip()
        return _set_intervals(short_str, long_str)

def _set_intervals(short_str: str, long_str: str) -> str:
    try:
        short_val = int(short_str)
        long_val = int(long_str)
    except ValueError:
        return "단기 및 장기 값은 정수여야 합니다."
        
    if not (1 <= short_val <= 60) or not (1 <= long_val <= 60):
        return "단기 및 장기 값은 1에서 60 사이의 정수여야 합니다."
        
    if short_val >= long_val:
        return "단기 분봉 값은 장기 분봉 값보다 작아야 합니다."
        
    s1 = set_setting("ddcrs_short", short_val)
    s2 = set_setting("ddcrs_long", long_val)
    
    if s1 and s2:
        return f"✅ 데드크로스 분봉 설정 완료\n━━━━━━━━━━━━━━━━━━━\n• 단기 분봉: {short_val}분\n• 장기 분봉: {long_val}분\n━━━━━━━━━━━━━━━━━━━"
    else:
        return "❌ 설정 저장 중 오류가 발생했습니다."
