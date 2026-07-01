import time
import logging
import threading
from api.session import session
from api.stock import get_daily_balance_ratio
from api.order import sell_stock
from utils.settings import get_setting, set_setting
from utils.stock_code import clean_stock_code

logger = logging.getLogger(__name__)

class TRSTManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TRSTManager, cls).__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        self.active = False
        self.tracked_stocks = {}  # { "stk_cd": { "buy_uv": float, "qty": int, "max_price": float, "is_selling": bool } }
        self.drop_ratio = 0.0
        self.min_profit = 0.0
        self.lock = threading.Lock()
        self.sync_thread = None

    def start(self, chat_id=None) -> str:
        with self.lock:
            if self.active:
                return "⚠️ 트레일링 스탑 감시가 이미 실행 중입니다."
            
            if not session.is_logged_in():
                return "❌ 로그인이 필요합니다. 먼저 로그인 명령어를 실행하세요."
            
            if chat_id:
                session.chat_id = chat_id
                
            self.drop_ratio = float(get_setting("trailing_stop_drop_ratio", 2.0))
            self.min_profit = float(get_setting("trailing_stop_min_profit", 4.5))
            
            self.active = True
            set_setting("trst_active", True)
            self.tracked_stocks.clear()
            
            from telegram.bot import reply_message
            from config.config import telegram_chat_id
            target_chat = chat_id or getattr(session, "chat_id", None) or telegram_chat_id
            if target_chat:
                msg = (
                    f"✅ 실시간 트레일링 스탑 감시를 시작합니다.\n"
                    f"- 고점 대비 하락율: {self.drop_ratio}%\n"
                    f"- 최소 발동 수익률: {self.min_profit}%"
                )
                reply_message(target_chat, msg)

            self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
            self.sync_thread.start()
            
            logger.info(f"트레일링 스탑 감시 시작: 하락율={self.drop_ratio}%, 최소 발동={self.min_profit}%")
            return ""

    def stop(self) -> str:
        with self.lock:
            if not self.active:
                return "⚠️ 트레일링 스탑 감시가 현재 실행 중이지 않습니다."
            
            self.active = False
            set_setting("trst_active", False)
            logger.info("트레일링 스탑 감시 중지 요청됨")
            
            from realtime.websocket_manager import WebsocketManager
            ws_manager = WebsocketManager()
            for stk_cd in list(self.tracked_stocks.keys()):
                ws_manager.unregister(stk_cd, self._process_tick)
                
            self.tracked_stocks.clear()
            return "🛑 실시간 트레일링 스탑 감시를 중단했습니다."

    def _sync_loop(self):
        logger.info("보유종목 동기화 루프(TRST) 시작")
        from realtime.websocket_manager import WebsocketManager
        ws_manager = WebsocketManager()
        
        while self.active:
            try:
                with self.lock:
                    self.drop_ratio = float(get_setting("trailing_stop_drop_ratio", 2.0))
                    self.min_profit = float(get_setting("trailing_stop_min_profit", 4.5))

                if session.mode == "paper":
                    from api.stock import get_account_evaluation
                    res = get_account_evaluation()
                    buy_prc_key = "avg_prc"
                else:
                    res = get_daily_balance_ratio()
                    buy_prc_key = "buy_uv"
                    
                if res.get("success"):
                    holdings = res.get("holdings", [])
                    current_codes = set()
                    
                    with self.lock:
                        for h in holdings:
                            stk_cd = h.get("stk_cd")
                            if not stk_cd:
                                continue
                            stk_cd = clean_stock_code(stk_cd)
                            current_codes.add(stk_cd)
                            
                            try:
                                buy_uv = float(h.get(buy_prc_key, 0.0))
                                qty = int(h.get("rmnd_qty", 0))
                            except (ValueError, TypeError):
                                continue
                            
                            if qty <= 0:
                                continue
                                
                            if stk_cd not in self.tracked_stocks:
                                self.tracked_stocks[stk_cd] = {
                                    "buy_uv": buy_uv,
                                    "qty": qty,
                                    "max_price": 0.0,
                                    "is_selling": False
                                }
                                logger.info(f"[TRST] 새로운 감시 종목 추가: {stk_cd} (평단: {buy_uv}, 수량: {qty})")
                                ws_manager.register(stk_cd, self._process_tick)
                            else:
                                self.tracked_stocks[stk_cd]["buy_uv"] = buy_uv
                                self.tracked_stocks[stk_cd]["qty"] = qty
                        
                        removed_codes = set(self.tracked_stocks.keys()) - current_codes
                        for r_code in removed_codes:
                            logger.info(f"[TRST] 감시 대상 제외: {r_code}")
                            del self.tracked_stocks[r_code]
                            ws_manager.unregister(r_code, self._process_tick)
                            
                else:
                    logger.error(f"[TRST] 보유종목 동기화 실패: {res.get('error_msg')}")
            except Exception as e:
                logger.error(f"[TRST] 보유종목 동기화 루프 오류: {e}")
                
            time.sleep(15)

    def _process_tick(self, data):
        stk_cd = data.get("symbol") or data.get("stk_cd") or data.get("item")
        if not stk_cd:
            return
        stk_cd = clean_stock_code(stk_cd)
            
        raw_price = data.get("values", {}).get("10")
        if not raw_price:
            return
            
        try:
            price_str = str(raw_price).replace("+", "").replace("-", "").strip()
            current_price = int(float(price_str))
        except ValueError:
            logger.error(f"현재가 형변환 실패: {raw_price}")
            return

        with self.lock:
            # 설정값 실시간 반영
            self.drop_ratio = float(get_setting("trailing_stop_drop_ratio", 2.0))
            self.min_profit = float(get_setting("trailing_stop_min_profit", 4.5))

            stock_info = self.tracked_stocks.get(stk_cd)
            if not stock_info or stock_info.get("is_selling"):
                return
                
            buy_uv = stock_info.get("buy_uv", 0.0)
            qty = stock_info.get("qty", 0)
            max_price = stock_info.get("max_price", 0.0)
            
            if buy_uv <= 0 or qty <= 0:
                return

            # 최고가 관리
            if max_price <= 0.0 or current_price > max_price:
                max_price = float(current_price)
                stock_info["max_price"] = max_price

            # 최소 발동 기준가 계산
            min_profit_price = buy_uv * (1 + self.min_profit / 100)
            
            # 고점 대비 하락 기준가 계산
            drop_trigger_price = max_price * (1 - self.drop_ratio / 100)
            
            # 손익률 계산
            pl_rt = ((current_price - buy_uv) / buy_uv) * 100.0
            max_pl_rt = ((max_price - buy_uv) / buy_uv) * 100.0

            # 감시 조건 체크
            # 1. 고가가 최소 발동 기준가 이상 도달한 적이 있어야 함
            # 2. 현재가가 고가 대비 하락율 조건 이하로 떨어졌을 때
            has_met_min_profit = (max_price >= min_profit_price)
            has_dropped_from_peak = (current_price <= drop_trigger_price)

            if has_met_min_profit and has_dropped_from_peak:
                stock_info["is_selling"] = True
                logger.info(
                    f"🚨 트레일링 스탑 조건 만족: {stk_cd} | "
                    f"현재가: {current_price:,}원 | 최고가: {max_price:,}원 | "
                    f"최고수익률: {max_pl_rt:.2f}% | 현재수익률: {pl_rt:.2f}%"
                )
                
                threading.Thread(
                    target=self._execute_sell,
                    args=(stk_cd, qty, current_price, max_price, buy_uv, pl_rt, max_pl_rt),
                    daemon=True
                ).start()

    def _execute_sell(self, stk_cd, qty, current_price, max_price, buy_uv, pl_rt, max_pl_rt):
        logger.info(f"[TRST] 주식 시장가 매도 실행: {stk_cd}, 수량: {qty}")
        res = sell_stock(stk_cd, qty)
        logger.info(f"[TRST] 매도 주문 응답 결과: {res}")
        
        chat_id = getattr(session, "chat_id", None)
        if not chat_id:
            logger.error("[TRST] 텔레그램 알림 전송 실패: session.chat_id가 설정되지 않음")
            return
            
        if res.get("success"):
            body = res["data"].get("body", res["data"])
            ord_no = body.get("ord_no", "알수없음")
            msg = (
                f"🚨 [트레일링 스탑 매도 실행]\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"종목코드: {stk_cd}\n"
                f"구분: 트레일링 스탑 조건 만족\n"
                f"현재수익률: {pl_rt:.2f}%\n"
                f"최고수익률: {max_pl_rt:.2f}%\n"
                f"평균단가: {buy_uv:,}원\n"
                f"현재가: {current_price:,}원\n"
                f"최고가: {max_price:,}원\n"
                f"매도수량: {qty:,}주 (시장가)\n"
                f"주문번호: {ord_no}\n"
                f"━━━━━━━━━━━━━━━━━━━"
            )
        else:
            msg = (
                f"❌ [트레일링 스탑 매도 주문 실패]\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"종목코드: {stk_cd}\n"
                f"현재수익률: {pl_rt:.2f}% (최고: {max_pl_rt:.2f}%)\n"
                f"실패 사유: {res.get('error_msg')}\n"
                f"━━━━━━━━━━━━━━━━━━━"
            )
            with self.lock:
                if stk_cd in self.tracked_stocks:
                    self.tracked_stocks[stk_cd]["is_selling"] = False
                    
        from telegram.bot import reply_message
        reply_message(chat_id, msg)
