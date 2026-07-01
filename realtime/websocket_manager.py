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
            logger.info("공용 웹소켓 매니저가 중지되었습니다.")

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

    def _subscribe_stock(self, stk_cd):
        with self.lock:
            if self.loop and self.websocket and stk_cd not in self.registered_codes:
                self.registered_codes.add(stk_cd)
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
                    
                    login_resp = await ws.recv()
                    logger.info(f"공용 웹소켓 로그인 응답 수신: {login_resp}")
                    
                    # 연결 복구 시 현재 등록되어 있는 모든 코드 재구독
                    with self.lock:
                        for stk_cd in self.subscribers.keys():
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
                                        self._dispatch_tick(tick)
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
