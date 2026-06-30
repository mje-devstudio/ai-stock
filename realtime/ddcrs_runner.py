import time
import json
import logging
import threading
import asyncio
import websockets
import datetime
from api.session import session
from api.stock import get_daily_balance_ratio
from api.order import sell_stock
from utils.settings import get_setting, set_setting
from utils.stock_code import clean_stock_code

logger = logging.getLogger(__name__)

class DDCRSManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DDCRSManager, cls).__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        self.active = False
        self.tracked_stocks = {}  # { "stk_cd": { "buy_uv": float, "qty": int, "is_selling": bool } }
        self.candles_history = {}  # { "stk_cd": [ {"time": str, "open": int, "high": int, "low": int, "close": int} ] }
        self.short_period = 5
        self.long_period = 20
        self.lock = threading.RLock()
        
        self.loop = None
        self.ws_thread = None
        self.sync_thread = None
        self.websocket = None
        
        self.subscribed_codes = set()

    def start(self, chat_id=None) -> str:
        with self.lock:
            if self.active:
                return "⚠️ 데드크로스 감시가 이미 실행 중입니다."
            
            if not session.is_logged_in():
                return "❌ 로그인이 필요합니다. 먼저 로그인 명령어를 실행하세요."
            
            if chat_id:
                session.chat_id = chat_id
                
            self.short_period = int(get_setting("ddcrs_short", 5))
            self.long_period = int(get_setting("ddcrs_long", 20))
            
            self.active = True
            self.tracked_stocks.clear()
            self.candles_history.clear()
            self.subscribed_codes.clear()
            
            # Save active state to settings
            set_setting("ddcrs_active", True)
            
        # Perform initial sync
        self._sync_holdings()
        
        with self.lock:
            # Start sync thread
            self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
            self.sync_thread.start()
            
            # Start websocket thread
            self.ws_thread = threading.Thread(target=self._ws_event_loop_runner, daemon=True)
            self.ws_thread.start()
            
            num_stocks = len(self.tracked_stocks)
            
        logger.info(f"데드크로스 감시 시작: 단기={self.short_period}분선, 장기={self.long_period}분선")
        return f"✅ 실시간 데드크로스 감시를 시작합니다.\n- 단기 이평: {self.short_period}분선\n- 장기 이평: {self.long_period}분선\n- 감시 종목 수: {num_stocks}개"

    def stop(self) -> str:
        with self.lock:
            if not self.active:
                return "⚠️ 데드크로스 감시가 현재 실행 중이지 않습니다."
            
            self.active = False
            set_setting("ddcrs_active", False)
            logger.info("데드크로스 감시 중지 요청됨")
            
            if self.loop and self.websocket:
                asyncio.run_coroutine_threadsafe(self._close_websocket(), self.loop)
                
            self.tracked_stocks.clear()
            self.candles_history.clear()
            self.subscribed_codes.clear()
            return "🛑 실시간 데드크로스 감시를 중단했습니다."

    def _init_candles(self, stk_cd):
        """ka10080 TR을 호출하여 초기 분봉 데이터를 동기화합니다."""
        logger.info(f"[{stk_cd}] 데드크로스 초기 분봉 데이터 동기화 시도...")
        from api.stock import get_min_chart
        
        # 1분봉으로 조회
        res = get_min_chart(stk_cd, tic_scope="1")
        if not res.get("success"):
            logger.error(f"[{stk_cd}] 초기 분봉 데이터 조회 실패: {res.get('error_msg')}")
            return False
            
        data = res.get("data", {})
        chart_list = data.get("stk_min_pole_chart_qry", [])
        if not chart_list:
            logger.warning(f"[{stk_cd}] 분봉 차트 데이터가 존재하지 않습니다.")
            return False
            
        parsed_candles = []
        for item in reversed(chart_list):
            cntr_tm = item.get("cntr_tm")  # YYYYMMDDHHmmss
            if not cntr_tm or len(cntr_tm) < 12:
                continue
            minute_key = cntr_tm[:12]  # YYYYMMDDHHmm
            
            try:
                close_val = int(str(item.get("cur_prc", 0)).strip().lstrip('+-'))
                open_val = int(str(item.get("open_pric", 0)).strip().lstrip('+-'))
                high_val = int(str(item.get("high_pric", 0)).strip().lstrip('+-'))
                low_val = int(str(item.get("low_pric", 0)).strip().lstrip('+-'))
            except ValueError:
                continue
                
            parsed_candles.append({
                "time": minute_key,
                "open": open_val,
                "high": high_val,
                "low": low_val,
                "close": close_val
            })
            
        with self.lock:
            self.candles_history[stk_cd] = parsed_candles[-100:]
            logger.info(f"[{stk_cd}] 데드크로스 초기 분봉 데이터 동기화 완료: {len(self.candles_history[stk_cd])}개 캔들 로드됨")
        return True

    def _sync_holdings(self):
        """계좌 보유 종목을 가져와 tracked_stocks와 동기화합니다."""
        try:
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
                                "is_selling": False,
                                "stk_nm": h.get("stk_nm", "")
                            }
                        else:
                            self.tracked_stocks[stk_cd]["buy_uv"] = buy_uv
                            self.tracked_stocks[stk_cd]["qty"] = qty
                            self.tracked_stocks[stk_cd]["stk_nm"] = h.get("stk_nm", self.tracked_stocks[stk_cd].get("stk_nm", ""))
                            
                # Load candles and subscribe for new codes
                for stk_cd in current_codes:
                    if stk_cd not in self.candles_history:
                        success = self._init_candles(stk_cd)
                        if success:
                            self._subscribe_stock(stk_cd)
                            
                # Handle removed codes (sold or closed)
                with self.lock:
                    removed_codes = set(self.tracked_stocks.keys()) - current_codes
                    for r_code in removed_codes:
                        logger.info(f"데드크로스 감시 제외 (보유종목 매도됨): {r_code}")
                        if r_code in self.tracked_stocks:
                            del self.tracked_stocks[r_code]
                        if r_code in self.candles_history:
                            del self.candles_history[r_code]
                        self._unsubscribe_stock(r_code)
            else:
                logger.error(f"데드크로스 보유종목 조회 실패: {res.get('error_msg')}")
        except Exception as e:
            logger.error(f"데드크로스 보유종목 동기화 중 오류: {e}")

    def _sync_loop(self):
        logger.info("데드크로스 보유종목 동기화 루프 시작")
        while self.active:
            try:
                # Reload periods
                with self.lock:
                    self.short_period = int(get_setting("ddcrs_short", 5))
                    self.long_period = int(get_setting("ddcrs_long", 20))
                    
                self._sync_holdings()
            except Exception as e:
                logger.error(f"데드크로스 동기화 루프 오류: {e}")
                
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
                
            logger.info(f"데드크로스 웹소켓 연결 시도: {host}")
            
            with self.lock:
                self.subscribed_codes.clear()
                self.websocket = None
            
            try:
                async with websockets.connect(host) as ws:
                    self.websocket = ws
                    logger.info("데드크로스 웹소켓 연결 완료. 로그인 패킷 전송 중...")
                    
                    login_packet = {
                        "trnm": "LOGIN",
                        "token": session.token
                    }
                    await ws.send(json.dumps(login_packet))
                    
                    login_resp = await ws.recv()
                    logger.info(f"데드크로스 로그인 응답 수신: {login_resp}")
                    
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
                            logger.error(f"데드크로스 웹소켓 메시지 파싱 에러: {message}")
                        except Exception as e:
                            logger.error(f"데드크로스 웹소켓 메시지 처리 에러: {e}")
                            
            except websockets.exceptions.ConnectionClosed:
                logger.warning("데드크로스 웹소켓 연결이 끊겼습니다. 재연결을 시도합니다.")
            except Exception as e:
                logger.error(f"데드크로스 웹소켓 오류 발생: {e}")
            finally:
                with self.lock:
                    self.subscribed_codes.clear()
                    self.websocket = None
                
            if self.active:
                logger.info(f"데드크로스 {retry_delay}초 후 웹소켓 재연결 시도...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)

    async def _close_websocket(self):
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("데드크로스 웹소켓 연결이 정상 종료되었습니다.")
            except Exception as e:
                logger.error(f"데드크로스 웹소켓 종료 중 오류: {e}")
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
            logger.info(f"데드크로스 웹소켓 실시간 등록(REG) 전송: {stk_cd}")

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
            logger.info(f"데드크로스 웹소켓 실시간 해제(REMOVE) 전송: {stk_cd}")

    def _calculate_ma(self, candles, period):
        if len(candles) < period:
            return None
        closes = [c["close"] for c in candles[-period:]]
        return sum(closes) / period

    async def _process_tick(self, data):
        stk_cd = data.get("symbol") or data.get("stk_cd") or data.get("item")
        if not stk_cd:
            return
        stk_cd = clean_stock_code(stk_cd)
        
        raw_price = data.get("values", {}).get("10")
        raw_time = data.get("values", {}).get("20")  # HHmmss
        if not raw_price or not raw_time:
            return
            
        try:
            price_str = str(raw_price).replace("+", "").replace("-", "").strip()
            current_price = int(float(price_str))
        except ValueError:
            logger.error(f"현재가 형변환 실패: {raw_price}")
            return
            
        today_str = datetime.datetime.now().strftime("%Y%m%d")
        if len(raw_time) >= 4:
            minute_key = today_str + raw_time[:4]
        else:
            minute_key = today_str + datetime.datetime.now().strftime("%H%M")
            
        with self.lock:
            if stk_cd not in self.tracked_stocks:
                return
            stock_info = self.tracked_stocks[stk_cd]
            if stock_info.get("is_selling"):
                return
                
            qty = stock_info.get("qty", 0)
            if qty <= 0:
                return
                
            if stk_cd not in self.candles_history:
                self.candles_history[stk_cd] = []
                
            candles = self.candles_history[stk_cd]
            
            if not candles:
                candles.append({
                    "time": minute_key,
                    "open": current_price,
                    "high": current_price,
                    "low": current_price,
                    "close": current_price
                })
            else:
                last_candle = candles[-1]
                if minute_key == last_candle["time"]:
                    last_candle["close"] = current_price
                    last_candle["high"] = max(last_candle["high"], current_price)
                    last_candle["low"] = min(last_candle["low"], current_price)
                elif minute_key > last_candle["time"]:
                    candles.append({
                        "time": minute_key,
                        "open": current_price,
                        "high": current_price,
                        "low": current_price,
                        "close": current_price
                    })
                    self.candles_history[stk_cd] = candles[-100:]
                    candles = self.candles_history[stk_cd]
                    
            S = self.short_period
            L = self.long_period
            
            if len(candles) < L + 1:
                return
                
            prev_candles = candles[:-1]
            prev_short_ma = self._calculate_ma(prev_candles, S)
            prev_long_ma = self._calculate_ma(prev_candles, L)
            
            curr_short_ma = self._calculate_ma(candles, S)
            curr_long_ma = self._calculate_ma(candles, L)
            
            if prev_short_ma is None or prev_long_ma is None or curr_short_ma is None or curr_long_ma is None:
                return
                
            # Dead Cross Check: prev_short >= prev_long AND curr_short < curr_long
            if prev_short_ma >= prev_long_ma and curr_short_ma < curr_long_ma:
                stock_info["is_selling"] = True
                
                logger.info(
                    f"💀 [데드크로스 감지] {stk_cd} | "
                    f"이전 MA({S}): {prev_short_ma:.2f} / MA({L}): {prev_long_ma:.2f} | "
                    f"현재 MA({S}): {curr_short_ma:.2f} / MA({L}): {curr_long_ma:.2f} | "
                    f"보유수량: {qty:,}주"
                )
                
                threading.Thread(
                    target=self._execute_sell,
                    args=(stk_cd, qty, prev_short_ma, prev_long_ma, curr_short_ma, curr_long_ma),
                    daemon=True
                ).start()

    def _execute_sell(self, stk_cd, qty, prev_short, prev_long, curr_short, curr_long):
        with self.lock:
            stk_nm = self.tracked_stocks.get(stk_cd, {}).get("stk_nm", "")
        name_str = f" ({stk_nm})" if stk_nm else ""
        logger.info(f"데드크로스 매도 주문 실행: {stk_cd}{name_str}, 수량: {qty}")
        
        chat_id = getattr(session, "chat_id", None)
        if not chat_id:
            logger.error("텔레그램 알림 전송 실패: session.chat_id가 설정되지 않음")
            return
            
        from telegram.bot import reply_message
        reply_message(
            chat_id, 
            f"💀 [데드크로스 발생 - 매도 진행]\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"종목명: {stk_nm if stk_nm else '알수없음'}\n"
            f"종목코드: {stk_cd}\n"
            f"보유수량: {qty:,}주\n"
            f"이전 MA: {prev_short:.1f} / {prev_long:.1f}\n"
            f"현재 MA: {curr_short:.1f} / {curr_long:.1f}\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        
        res = sell_stock(stk_cd, qty)
        logger.info(f"데드크로스 매도 주문 응답: {res}")
        
        if res.get("success"):
            body = res["data"].get("body", res["data"])
            ord_no = body.get("ord_no", "알수없음")
            msg = (
                f"🚨 [데드크로스 매도 주문 완료]\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"종목명: {stk_nm if stk_nm else '알수없음'}\n"
                f"종목코드: {stk_cd}\n"
                f"매도수량: {qty:,}주 (시장가)\n"
                f"주문번호: {ord_no}\n"
                f"━━━━━━━━━━━━━━━━━━━"
            )
        else:
            msg = (
                f"❌ [데드크로스 매도 주문 실패]\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"종목명: {stk_nm if stk_nm else '알수없음'}\n"
                f"종목코드: {stk_cd}\n"
                f"실패 사유: {res.get('error_msg')}\n"
                f"━━━━━━━━━━━━━━━━━━━"
            )
            with self.lock:
                if stk_cd in self.tracked_stocks:
                    self.tracked_stocks[stk_cd]["is_selling"] = False
                    
        reply_message(chat_id, msg)
