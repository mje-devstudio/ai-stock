import time
import json
import logging
import threading
import asyncio
import websockets
import requests
from api.session import session
from api.stock import get_daily_balance_ratio
from api.order import sell_stock
from utils.settings import get_setting
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
        
        self.loop = None
        self.ws_thread = None
        self.sync_thread = None
        self.websocket = None
        
        self.subscribed_codes = set()

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
            self.tracked_stocks.clear()
            self.subscribed_codes.clear()
            
            # Start sync thread
            self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
            self.sync_thread.start()
            
            # Start websocket thread
            self.ws_thread = threading.Thread(target=self._ws_event_loop_runner, daemon=True)
            self.ws_thread.start()
            
            logger.info(f"스탑로스 감시 시작: tpr={self.tpr}%, slr={self.slr}%")
            return f"✅ 실시간 스탑로스 감시를 시작합니다.\n- 익절 기준(tpr): {self.tpr}%\n- 손절 기준(slr): {self.slr}%"

    def stop(self) -> str:
        with self.lock:
            if not self.active:
                return "⚠️ 스탑로스 감시가 현재 실행 중이지 않습니다."
            
            self.active = False
            logger.info("스탑로스 감시 중지 요청됨")
            
            if self.loop and self.websocket:
                asyncio.run_coroutine_threadsafe(self._close_websocket(), self.loop)
                
            self.tracked_stocks.clear()
            self.subscribed_codes.clear()
            return "🛑 실시간 스탑로스 감시를 중단했습니다."

    def _sync_loop(self):
        logger.info("보유종목 동기화 루프 시작")
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
                                self._subscribe_stock(stk_cd)
                            else:
                                self.tracked_stocks[stk_cd]["buy_uv"] = buy_uv
                                self.tracked_stocks[stk_cd]["qty"] = qty
                        
                        removed_codes = set(self.tracked_stocks.keys()) - current_codes
                        for r_code in removed_codes:
                            logger.info(f"감시 대상 제외: {r_code}")
                            del self.tracked_stocks[r_code]
                            self._unsubscribe_stock(r_code)
                            
                else:
                    logger.error(f"보유종목 동기화 실패: {res.get('error_msg')}")
            except Exception as e:
                logger.error(f"보유종목 동기화 루프 오류: {e}")
                
            time.sleep(15)

    def _ws_event_loop_runner(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._websocket_listener())
        self.loop.close()

    async def _websocket_listener(self):
        retry_delay = 5
        while self.active:
            if session.mode == "paper":
                host = "wss://mockapi.kiwoom.com:10000/api/dostk/websocket"
            else:
                host = "wss://api.kiwoom.com:10000/api/dostk/websocket"
                
            logger.info(f"웹소켓 연결 시도: {host}")
            
            with self.lock:
                self.subscribed_codes.clear()
                self.websocket = None
            
            try:
                async with websockets.connect(host) as ws:
                    self.websocket = ws
                    logger.info("웹소켓 연결 완료. 로그인 패킷 전송 중...")
                    
                    login_packet = {
                        "trnm": "LOGIN",
                        "token": session.token
                    }
                    await ws.send(json.dumps(login_packet))
                    
                    login_resp = await ws.recv()
                    logger.info(f"로그인 응답 수신: {login_resp}")
                    
                    # Re-subscribe existing codes on reconnect
                    with self.lock:
                        for stk_cd in self.tracked_stocks.keys():
                            self._subscribe_stock(stk_cd)
                            
                    retry_delay = 5
                    
                    async for message in ws:
                        if not self.active:
                            break
                        try:
                            root_data = json.loads(message)
                            if root_data.get("trnm") == "REAL":
                                tick_list = root_data.get("data", [])
                                for tick in tick_list:
                                    if tick.get("type") == "0B":
                                        await self._process_tick(tick)
                        except json.JSONDecodeError:
                            logger.error(f"웹소켓 메시지 파싱 에러: {message}")
                        except Exception as e:
                            logger.error(f"웹소켓 메시지 처리 에러: {e}")
                            
            except websockets.exceptions.ConnectionClosed:
                logger.warning("웹소켓 연결이 끊겼습니다. 재연결을 시도합니다.")
            except Exception as e:
                logger.error(f"웹소켓 오류 발생: {e}")
            finally:
                with self.lock:
                    self.subscribed_codes.clear()
                    self.websocket = None
                
            if self.active:
                logger.info(f"{retry_delay}초 후 웹소켓 재연결 시도...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)

    async def _close_websocket(self):
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("웹소켓 연결이 정상 종료되었습니다.")
            except Exception as e:
                logger.error(f"웹소켓 종료 중 오류: {e}")
            self.websocket = None

    def _subscribe_stock(self, stk_cd):
        stk_cd = clean_stock_code(stk_cd)
        if self.loop and self.websocket and stk_cd not in self.subscribed_codes:
            self.subscribed_codes.add(stk_cd)
            reg_packet = {
                "trnm": "REG",
                "grp_no": "1",
                "refresh": "1",
                "data": [
                    {
                        "item": [stk_cd],
                        "type": ["0B"]
                    }
                ]
            }
            asyncio.run_coroutine_threadsafe(self.websocket.send(json.dumps(reg_packet)), self.loop)
            logger.info(f"웹소켓 실시간 등록(REG) 전송: {stk_cd}")

    def _unsubscribe_stock(self, stk_cd):
        stk_cd = clean_stock_code(stk_cd)
        if self.loop and self.websocket and stk_cd in self.subscribed_codes:
            self.subscribed_codes.discard(stk_cd)
            remove_packet = {
                "trnm": "REMOVE",
                "grp_no": "1",
                "data": [
                    {
                        "item": [stk_cd],
                        "type": ["0B"]
                    }
                ]
            }
            asyncio.run_coroutine_threadsafe(self.websocket.send(json.dumps(remove_packet)), self.loop)
            logger.info(f"웹소켓 실시간 해제(REMOVE) 전송: {stk_cd}")

    async def _process_tick(self, data):
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
        # Verify thread session state and token
        logger.info(f"매도 실행 스레드 세션 검증: logged_in={session.is_logged_in()}, mode={session.mode}, token_prefix={str(session.token)[:10] if session.token else 'None'}")
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
