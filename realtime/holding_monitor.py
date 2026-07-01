import time
import logging
import threading
from api.session import session
from api.stock import get_account_evaluation, get_daily_balance_ratio
from utils.stock_code import clean_stock_code

logger = logging.getLogger(__name__)

class HoldingsMonitor:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(HoldingsMonitor, cls).__new__(cls)
                cls._instance._init_monitor()
            return cls._instance

    def _init_monitor(self):
        self.active = False
        self.last_holdings = {}
        self.lock = threading.Lock()
        self.monitor_thread = None

    def start(self, chat_id=None) -> str:
        with self.lock:
            if self.active:
                return "⚠️ 보유 종목 모니터링이 이미 실행 중입니다."
            
            if not session.is_logged_in():
                return "❌ 로그인이 필요합니다."
                
            self.active = True
            self.last_holdings.clear()
            
            # 최초 보유 종목 수집
            res = self._fetch_holdings()
            if res.get("success"):
                holdings = res.get("holdings", [])
                self.last_holdings = {}
                for h in holdings:
                    stk_cd = h.get("stk_cd")
                    if not stk_cd:
                        continue
                    stk_cd = clean_stock_code(stk_cd)
                    avg_prc, cur_prc = self._parse_prices(h)
                    self.last_holdings[stk_cd] = {
                        "stk_nm": h.get("stk_nm", h["stk_cd"]),
                        "qty": int(h.get("rmnd_qty", 0)),
                        "avg_prc": avg_prc,
                        "cur_prc": cur_prc
                    }
                logger.info(f"[HoldingsMonitor] 최초 보유 종목 로드 완료: {self.last_holdings}")
            else:
                logger.warning(f"[HoldingsMonitor] 최초 보유 종목 조회 실패: {res.get('error_msg')}")
                
            self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(chat_id,), daemon=True)
            self.monitor_thread.start()
            logger.info("보유 종목 모니터링 스레드가 기동되었습니다.")
            return ""

    def stop(self) -> str:
        with self.lock:
            if not self.active:
                return "⚠️ 모니터링이 실행 중이지 않습니다."
            self.active = False
            logger.info("보유 종목 모니터링 중지 요청됨")
            return "🛑 보유 종목 모니터링을 중단했습니다."

    def _fetch_holdings(self) -> dict:
        if getattr(session, 'mode', 'real') == 'paper':
            return get_account_evaluation()
        else:
            return get_daily_balance_ratio()

    def _parse_prices(self, h) -> tuple:
        """
        보유 종목 딕셔너리에서 평균단가와 현재가를 안전하게 파싱하여 반환합니다.
        """
        # 평균단가 (avg_prc, buy_uv, pchs_avg_pric)
        avg_prc_val = h.get("avg_prc") or h.get("buy_uv") or h.get("pchs_avg_pric") or 0.0
        try:
            avg_prc = float(str(avg_prc_val).strip().lstrip('+-'))
        except (ValueError, TypeError):
            avg_prc = 0.0
            
        # 현재가 (cur_prc, now_pric, evlt_prc, cur_price)
        cur_prc_val = h.get("cur_prc") or h.get("now_pric") or h.get("evlt_prc") or h.get("cur_price") or 0.0
        try:
            cur_prc = float(str(cur_prc_val).strip().lstrip('+-'))
        except (ValueError, TypeError):
            cur_prc = 0.0
            
        return avg_prc, cur_prc

    def _monitor_loop(self, chat_id):
        from telegram.bot import reply_message
        from config.config import telegram_chat_id
        target_chat = chat_id or getattr(session, "chat_id", None) or telegram_chat_id
        
        while self.active:
            try:
                time.sleep(10)
                if not self.active:
                    break
                    
                res = self._fetch_holdings()
                if not res.get("success"):
                    logger.error(f"[HoldingsMonitor] 보유 종목 조회 실패: {res.get('error_msg')}")
                    continue
                    
                holdings = res.get("holdings", [])
                current_holdings = {}
                for h in holdings:
                    stk_cd = h.get("stk_cd")
                    if not stk_cd:
                        continue
                    stk_cd = clean_stock_code(stk_cd)
                    avg_prc, cur_prc = self._parse_prices(h)
                    current_holdings[stk_cd] = {
                        "stk_nm": h.get("stk_nm", h["stk_cd"]),
                        "qty": int(h.get("rmnd_qty", 0)),
                        "avg_prc": avg_prc,
                        "cur_prc": cur_prc
                    }
                
                with self.lock:
                    all_keys = set(self.last_holdings.keys()) | set(current_holdings.keys())
                    
                    for stk_cd in all_keys:
                        last_qty = self.last_holdings.get(stk_cd, {}).get("qty", 0)
                        curr_qty = current_holdings.get(stk_cd, {}).get("qty", 0)
                        
                        if last_qty != curr_qty:
                            stk_nm = (
                                current_holdings.get(stk_cd, {}).get("stk_nm")
                                or self.last_holdings.get(stk_cd, {}).get("stk_nm")
                                or stk_cd
                            )
                            
                            # 신규 가격정보 추출
                            avg_prc = current_holdings.get(stk_cd, {}).get("avg_prc", 0.0) or self.last_holdings.get(stk_cd, {}).get("avg_prc", 0.0)
                            cur_prc = current_holdings.get(stk_cd, {}).get("cur_prc", 0.0) or self.last_holdings.get(stk_cd, {}).get("cur_prc", 0.0)
                            
                            diff = curr_qty - last_qty
                            if diff > 0:
                                prc_info = ""
                                if cur_prc > 0:
                                    prc_info += f"- 체결 단가(현재가): {int(cur_prc):,}원\n"
                                if avg_prc > 0:
                                    prc_info += f"- 보유 평단가: {int(avg_prc):,}원\n"
                                    
                                msg = (
                                    f"🔔 [주식 매수 완료 알림]\n"
                                    f"- 종목: {stk_nm} ({stk_cd})\n"
                                    f"- 기존 수량: {last_qty}주 -> 변경 수량: {curr_qty}주 (+{diff}주)\n"
                                    f"{prc_info.strip()}"
                                )
                                logger.info(msg)
                                if target_chat:
                                    reply_message(target_chat, msg)
                            elif diff < 0:
                                prc_info = ""
                                if cur_prc > 0:
                                    prc_info += f"- 체결 단가(현재가): {int(cur_prc):,}원\n"
                                if avg_prc > 0:
                                    prc_info += f"- 보유 평단가: {int(avg_prc):,}원\n"
                                    
                                msg = (
                                    f"🔔 [주식 매도 완료 알림]\n"
                                    f"- 종목: {stk_nm} ({stk_cd})\n"
                                    f"- 기존 수량: {last_qty}주 -> 변경 수량: {curr_qty}주 ({diff}주)\n"
                                    f"{prc_info.strip()}"
                                )
                                logger.info(msg)
                                if target_chat:
                                    reply_message(target_chat, msg)
                                
                                # 매도 기록을 쿨다운 매니저에 저장
                                try:
                                    from utils.cooldown import CooldownManager
                                    CooldownManager().record_sell(stk_cd)
                                except Exception as e:
                                    logger.error(f"[HoldingsMonitor] 쿨다운 기록 오류: {e}")
                                    
                    self.last_holdings = current_holdings
                    
            except Exception as e:
                logger.error(f"[HoldingsMonitor] 모니터링 루프 내 예외 발생: {e}")
                time.sleep(5)
