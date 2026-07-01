import time
import logging
import threading
from api.session import session
from api.stock import get_daily_balance_ratio
from api.order import sell_stock
from utils.settings import get_setting, set_setting
from utils.stock_code import clean_stock_code

logger = logging.getLogger(__name__)

class STLSManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(STLSManager, cls).__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        self.active = False
        self.tracked_stocks = {}  # { "stk_cd": { "buy_uv": float, "qty": int, "is_selling": bool } }
        self.tpr = 0.0
        self.slr = 0.0
        self.lock = threading.Lock()
        self.sync_thread = None

    def start(self, chat_id=None) -> str:
        with self.lock:
            if self.active:
                return "⚠️ 스탑로스 감시가 이미 실행 중입니다."
            
            if not session.is_logged_in():
                return "❌ 로그인이 필요합니다. 먼저 로그인 명령어를 실행하세요."
            
            if chat_id:
                session.chat_id = chat_id
                
            self.tpr = float(get_setting("take_profit_ratio", 0.0))
            self.slr = -abs(float(get_setting("stop_loss_ratio", 0.0)))
            
            self.active = True
            set_setting("stls_active", True)
            self.tracked_stocks.clear()
            
            # Start sync thread
            self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
            self.sync_thread.start()
            
            logger.info(f"스탑로스 감시 시작: tpr={self.tpr}%, slr={self.slr}%")
            return f"✅ 실시간 스탑로스 감시를 시작합니다.\n- 익절 기준(tpr): {self.tpr}%\n- 손절 기준(slr): {self.slr}%"

    def stop(self) -> str:
        with self.lock:
            if not self.active:
                return "⚠️ 스탑로스 감시가 현재 실행 중이지 않습니다."
            
            self.active = False
            set_setting("stls_active", False)
            logger.info("스탑로스 감시 중지 요청됨")
            
            from realtime.websocket_manager import WebsocketManager
            ws_manager = WebsocketManager()
            for stk_cd in list(self.tracked_stocks.keys()):
                ws_manager.unregister(stk_cd, self._process_tick)
                
            self.tracked_stocks.clear()
            return "🛑 실시간 스탑로스 감시를 중단했습니다."

    def _sync_loop(self):
        logger.info("보유종목 동기화 루프 시작")
        from realtime.websocket_manager import WebsocketManager
        ws_manager = WebsocketManager()
        
        while self.active:
            try:
                # Reload settings dynamically
                with self.lock:
                    self.tpr = float(get_setting("take_profit_ratio", 0.0))
                    self.slr = -abs(float(get_setting("stop_loss_ratio", 0.0)))

                # 모의투자(paper)의 경우 ka01690을 지원하지 않으므로 kt00004(get_account_evaluation)로 대체
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
                                    "is_selling": False
                                }
                                logger.info(f"새로운 감시 종목 추가: {stk_cd} (평단: {buy_uv}, 수량: {qty})")
                                ws_manager.register(stk_cd, self._process_tick)
                            else:
                                self.tracked_stocks[stk_cd]["buy_uv"] = buy_uv
                                self.tracked_stocks[stk_cd]["qty"] = qty
                        
                        removed_codes = set(self.tracked_stocks.keys()) - current_codes
                        for r_code in removed_codes:
                            logger.info(f"감시 대상 제외: {r_code}")
                            del self.tracked_stocks[r_code]
                            ws_manager.unregister(r_code, self._process_tick)
                            
                else:
                    logger.error(f"보유종목 동기화 실패: {res.get('error_msg')}")
            except Exception as e:
                logger.error(f"보유종목 동기화 루프 오류: {e}")
                
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

        # Ensure slr is negative before condition check
        self.slr = -abs(self.slr)

        with self.lock:
            stock_info = self.tracked_stocks.get(stk_cd)
            if not stock_info or stock_info.get("is_selling"):
                return
                
            buy_uv = stock_info.get("buy_uv", 0.0)
            qty = stock_info.get("qty", 0)
            
            if buy_uv <= 0 or qty <= 0:
                return
                
            pl_rt = ((current_price - buy_uv) / buy_uv) * 100.0
            
            logger.info(f"📈 실시간 손익률 계산: {stk_cd} | 현재가: {current_price:,}원 | 평단: {buy_uv:,}원 | 손익률: {pl_rt:.2f}% (익절기준: {self.tpr}%, 손절기준: {self.slr}%)")
            
            trigger_tp = (self.tpr > 0.0 and pl_rt >= self.tpr)
            trigger_sl = (self.slr < 0.0 and pl_rt <= self.slr)
            
            if trigger_tp or trigger_sl:
                stock_info["is_selling"] = True
                
                trigger_type = "익절" if trigger_tp else "손절"
                limit_ratio = self.tpr if trigger_tp else self.slr
                
                logger.info(f"🚨 스탑로스 조건 만족 ({trigger_type}): {stk_cd} | 수익률: {pl_rt:.2f}% (기준: {limit_ratio}%)")
                
                threading.Thread(
                    target=self._execute_sell,
                    args=(stk_cd, qty, pl_rt, trigger_type, current_price),
                    daemon=True
                ).start()

    def _execute_sell(self, stk_cd, qty, pl_rt, trigger_type, current_price):
        logger.info(f"주식 시장가 매도 실행: {stk_cd}, 수량: {qty}")
        res = sell_stock(stk_cd, qty)
        logger.info(f"매도 주문 응답 결과: {res}")
        
        chat_id = getattr(session, "chat_id", None)
        if not chat_id:
            logger.error("텔레그램 알림 전송 실패: session.chat_id가 설정되지 않음")
            return
            
        if res.get("success"):
            body = res["data"].get("body", res["data"])
            ord_no = body.get("ord_no", "알수없음")
            msg = (
                f"🚨 [스탑로스 감시 매도 실행]\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"종목코드: {stk_cd}\n"
                f"구분: {trigger_type} 조건 달성\n"
                f"실시간 손익률: {pl_rt:.2f}%\n"
                f"현재가: {current_price:,}원\n"
                f"매도수량: {qty:,}주 (시장가)\n"
                f"주문번호: {ord_no}\n"
                f"━━━━━━━━━━━━━━━━━━━"
            )
        else:
            msg = (
                f"❌ [스탑로스 매도 주문 실패]\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"종목코드: {stk_cd}\n"
                f"구분: {trigger_type} 조건 달성 ({pl_rt:.2f}%)\n"
                f"실패 사유: {res.get('error_msg')}\n"
                f"━━━━━━━━━━━━━━━━━━━"
            )
            with self.lock:
                if stk_cd in self.tracked_stocks:
                    self.tracked_stocks[stk_cd]["is_selling"] = False
                    
        from telegram.bot import reply_message
        reply_message(chat_id, msg)
