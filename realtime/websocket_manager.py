import json
import logging
import threading
import asyncio
import websockets
from api.session import session
from utils.stock_code import clean_stock_code

logger = logging.getLogger(__name__)

class WebsocketManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(WebsocketManager, cls).__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        self.active = False
        self.websocket = None
        self.loop = None
        self.ws_thread = None
        self.lock = threading.RLock()
        self.subscribers = {}  # { stk_cd: set(callbacks) }
        self.registered_codes = set()
        self.cnsr_subscribers = {}  # { seq: set(callbacks) }
        self.registered_cnsr = set()
        self.cnsrlst_event = threading.Event()
        self.cnsrlst_data = None

    def start(self):
        with self.lock:
            if self.active:
                return
            self.active = True
            self.ws_thread = threading.Thread(target=self._ws_event_loop_runner, daemon=True)
            self.ws_thread.start()
            logger.info("공용 웹소켓 매니저가 기동되었습니다.")

    def stop(self):
        with self.lock:
            if not self.active:
                return
            self.active = False
            if self.loop and self.websocket:
                asyncio.run_coroutine_threadsafe(self._close_websocket(), self.loop)
            self.subscribers.clear()
            self.registered_codes.clear()
            self.cnsr_subscribers.clear()
            self.registered_cnsr.clear()
            logger.info("공용 웹소켓 매니저가 중지되었습니다.")

    def get_conditional_search_list(self, timeout=10) -> dict:
        """
        웹소켓 연결을 통해 조건검색 목록조회를 요청하고 결과를 동기적으로 대기하여 반환합니다.
        """
        with self.lock:
            if not self.active or not self.websocket:
                return {"success": False, "error_msg": "웹소켓이 연결되어 있지 않습니다. 자동매매 또는 실시간 감시(스탑로스/크로스)가 켜져 있는지 확인하십시오."}
            
            self.cnsrlst_event.clear()
            self.cnsrlst_data = None
            
            req_packet = {
                "trnm": "CNSRLST"
            }
            asyncio.run_coroutine_threadsafe(self.websocket.send(json.dumps(req_packet)), self.loop)
            logger.info("웹소켓을 통한 조건검색 목록조회(CNSRLST) 요청 전송 완료")
            
        success = self.cnsrlst_event.wait(timeout=timeout)
        if not success:
            return {"success": False, "error_msg": "조건식 조회 응답 시간 초과 (Timeout)"}
            
        if self.cnsrlst_data is None:
            return {"success": False, "error_msg": "조건식 조회 데이터가 없습니다."}
            
        return {"success": True, "data": self.cnsrlst_data}

    def register(self, stk_cd, callback):
        stk_cd = clean_stock_code(stk_cd)
        with self.lock:
            if stk_cd not in self.subscribers:
                self.subscribers[stk_cd] = set()
            self.subscribers[stk_cd].add(callback)
            
            # 매니저가 비활성 상태이면 기동
            if not self.active:
                self.start()
                
            # 웹소켓이 연결되어 있는 상태라면 실시간 구독 패킷 전송
            self._subscribe_stock(stk_cd)

    def unregister(self, stk_cd, callback):
        stk_cd = clean_stock_code(stk_cd)
        with self.lock:
            if stk_cd in self.subscribers:
                self.subscribers[stk_cd].discard(callback)
                if not self.subscribers[stk_cd]:
                    del self.subscribers[stk_cd]
                    self._unsubscribe_stock(stk_cd)

    def _send_bulk_subscribe(self):
        with self.lock:
            if not self.loop or not self.websocket or not self.subscribers:
                return
                
            stock_list = list(self.subscribers.keys())
            self.registered_codes.update(stock_list)
            
            chunk_size = 100
            for i in range(0, len(stock_list), chunk_size):
                chunk = stock_list[i:i+chunk_size]
                reg_packet = {
                    "trnm": "REG",
                    "grp_no": "1",
                    "refresh": "1" if i == 0 else "0",
                    "data": [
                        {
                            "item": chunk,
                            "type": ["0B"]
                        }
                    ]
                }
                asyncio.run_coroutine_threadsafe(self.websocket.send(json.dumps(reg_packet)), self.loop)
                logger.info(f"공용 웹소켓 실시간 등록(REG) 일괄 전송: {len(chunk)} 종목")

    def _subscribe_stock(self, stk_cd):
        with self.lock:
            if self.loop and self.websocket and stk_cd not in self.registered_codes:
                self.registered_codes.add(stk_cd)
                reg_packet = {
                    "trnm": "REG",
                    "grp_no": "1",
                    "refresh": "0",
                    "data": [
                        {
                            "item": [stk_cd],
                            "type": ["0B"]
                        }
                    ]
                }
                asyncio.run_coroutine_threadsafe(self.websocket.send(json.dumps(reg_packet)), self.loop)
                logger.info(f"공용 웹소켓 실시간 등록(REG) 전송: {stk_cd}")

    def _unsubscribe_stock(self, stk_cd):
        with self.lock:
            if self.loop and self.websocket and stk_cd in self.registered_codes:
                self.registered_codes.discard(stk_cd)
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
                logger.info(f"공용 웹소켓 실시간 해제(REMOVE) 전송: {stk_cd}")

    def request_conditional_search_realtime(self, seq, search_type="1", stex_tp="K"):
        """조건검색 실시간 요청(CNSRREQ)"""
        with self.lock:
            seq_str = str(seq)
            if self.loop and self.websocket and seq_str not in self.registered_cnsr:
                self.registered_cnsr.add(seq_str)
                req_packet = {
                    "trnm": "CNSRREQ",
                    "seq": seq_str,
                    "search_type": search_type,
                    "stex_tp": stex_tp
                }
                asyncio.run_coroutine_threadsafe(self.websocket.send(json.dumps(req_packet)), self.loop)
                logger.info(f"웹소켓 조건검색 실시간(CNSRREQ) 전송: seq={seq_str}")

    def register_cnsr(self, seq, callback):
        seq_str = str(seq)
        with self.lock:
            if seq_str not in self.cnsr_subscribers:
                self.cnsr_subscribers[seq_str] = set()
            self.cnsr_subscribers[seq_str].add(callback)
            
            if not self.active:
                self.start()
                
            self.request_conditional_search_realtime(seq_str)

    def unregister_cnsr(self, seq, callback):
        seq_str = str(seq)
        with self.lock:
            if seq_str in self.cnsr_subscribers:
                self.cnsr_subscribers[seq_str].discard(callback)
                if not self.cnsr_subscribers[seq_str]:
                    del self.cnsr_subscribers[seq_str]
                    # Note: ka10174 (CNSRREL) is not implemented yet. 
                    # For now we just remove the callback.

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
                
            logger.info(f"공용 웹소켓 연결 시도: {host}")
            
            with self.lock:
                self.registered_codes.clear()
                self.registered_cnsr.clear()
                self.websocket = None
            
            try:
                async with websockets.connect(host) as ws:
                    self.websocket = ws
                    logger.info("공용 웹소켓 연결 완료. 로그인 패킷 전송 중...")
                    
                    login_packet = {
                        "trnm": "LOGIN",
                        "token": session.token
                    }
                    await ws.send(json.dumps(login_packet))
                    
                    retry_delay = 5
                    
                    async for message in ws:
                        if not self.active:
                            break
                        try:
                            root_data = json.loads(message)
                            trnm = root_data.get("trnm")
                            
                            if trnm == "LOGIN":
                                logger.info(f"공용 웹소켓 로그인 응답 수신: {root_data}")
                                if str(root_data.get("return_code")) == "0":
                                    logger.info("웹소켓 로그인 성공. 조건검색 목록(CNSRLST) 조회를 시작합니다.")
                                    # 키움 웹소켓 구조상 CNSRREQ 전에 CNSRLST 호출이 필수임
                                    cnsrlst_req = {"trnm": "CNSRLST"}
                                    await ws.send(json.dumps(cnsrlst_req))
                                    
                                    # 종목 실시간 구독 복구
                                    with self.lock:
                                        self._send_bulk_subscribe()
                                else:
                                    logger.error(f"웹소켓 로그인 실패: {root_data.get('return_msg')}")
                                    break
                                continue
                            
                            if trnm == "CNSRLST":
                                self.cnsrlst_data = root_data
                                self.cnsrlst_event.set()
                                logger.info("조건검색 목록 수신 완료. 실시간 조건검색(CNSRREQ) 요청을 복구합니다.")
                                with self.lock:
                                    for seq in self.cnsr_subscribers.keys():
                                        self.request_conditional_search_realtime(seq)
                                continue
                                
                            if trnm == "CNSRREQ":
                                data_list = root_data.get("data")
                                seq = root_data.get("seq")
                                if data_list:
                                    jmcodes = [d.get("jmcode") for d in data_list]
                                    logger.info(f"조건식 {seq} 실시간 등록 성공. 초기 편입 종목 리스트: {jmcodes}")
                                else:
                                    logger.info(f"조건식 {seq} 실시간 등록 성공. 현재 편입된 종목 없음.")
                                continue
                                
                            if trnm == "PING":
                                await ws.send(message)
                                continue
                                
                            if trnm == "REAL":
                                tick_list = root_data.get("data", [])
                                for tick in tick_list:
                                    tick_type = tick.get("type")
                                    if tick_type == "0B":
                                        self._dispatch_tick(tick)
                                    elif tick_type == "02":
                                        self._dispatch_cnsr(tick)
                            else:
                                logger.info(f"실시간 시세 서버 응답 수신: {root_data}")
                        except json.JSONDecodeError:
                            logger.error(f"공용 웹소켓 메시지 파싱 에러: {message}")
                        except Exception as e:
                            logger.error(f"공용 웹소켓 메시지 처리 에러: {e}")
                            
            except websockets.exceptions.ConnectionClosed:
                logger.warning("공용 웹소켓 연결이 끊겼습니다. 재연결을 시도합니다.")
            except Exception as e:
                logger.error(f"공용 웹소켓 오류 발생: {e}")
            finally:
                with self.lock:
                    self.registered_codes.clear()
                    self.registered_cnsr.clear()
                    self.websocket = None
                
            if self.active:
                logger.info(f"공용 웹소켓 {retry_delay}초 후 재연결 시도...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)

    async def _close_websocket(self):
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("공용 웹소켓 연결이 정상 종료되었습니다.")
            except Exception as e:
                logger.error(f"공용 웹소켓 종료 중 오류: {e}")
            self.websocket = None

    def _dispatch_tick(self, tick):
        stk_cd = tick.get("symbol") or tick.get("stk_cd") or tick.get("item")
        if not stk_cd:
            return
        stk_cd = clean_stock_code(stk_cd)
        
        with self.lock:
            callbacks = list(self.subscribers.get(stk_cd, []))
            
        for cb in callbacks:
            try:
                cb(tick)
            except Exception as e:
                logger.error(f"공용 웹소켓 콜백 실행 오류 (종목: {stk_cd}): {e}")

    def _dispatch_cnsr(self, tick):
        # type "02" 에서 seq는 values의 "841"
        values = tick.get("values", {})
        seq = values.get("841")
        if not seq:
            return
            
        with self.lock:
            callbacks = list(self.cnsr_subscribers.get(str(seq), []))
            
        for cb in callbacks:
            try:
                cb(tick)
            except Exception as e:
                logger.error(f"조건검색 실시간 콜백 실행 오류 (seq: {seq}): {e}")
