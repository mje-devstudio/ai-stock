import logging
import threading
import queue
import time
from api.session import session
from utils.settings import set_setting
from utils.jggs import load_jggs_commands
from utils.market import is_market_open

logger = logging.getLogger(__name__)

class JGGSManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(JGGSManager, cls).__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        self.active = False
        self.lock = threading.Lock()
        self.registered_seqs = set()
        self.cmd_queue = queue.Queue()
        self.worker_thread = None

    def start(self, chat_id=None) -> str:
        with self.lock:
            if self.active:
                return "⚠️ 조건검색 자동매매가 이미 실행 중입니다."
            
            if not session.is_logged_in():
                return "❌ 로그인이 필요합니다. 먼저 로그인 명령어를 실행하세요."
                
            if chat_id:
                session.chat_id = chat_id
                
            commands = load_jggs_commands()
            if not commands:
                return "📋 등록된 조건식 배정 명령이 없습니다. 먼저 `jggs add`로 명령을 등록해주세요."
                
            self.active = True
            set_setting("jggs_active", True)
            
            # 이전 큐가 차있을 수 있으므로 비우기
            while not self.cmd_queue.empty():
                try:
                    self.cmd_queue.get_nowait()
                except queue.Empty:
                    break
                    
            # 1초당 요청 개수(최대 5개) 초과를 방지하기 위해 큐 처리 워커 구동
            self.worker_thread = threading.Thread(target=self._command_worker, daemon=True)
            self.worker_thread.start()
            
            from realtime.websocket_manager import WebsocketManager
            ws_manager = WebsocketManager()
            
            self.registered_seqs.clear()
            for item in commands:
                cond_id = str(item['cond_id'])
                if cond_id not in self.registered_seqs:
                    self.registered_seqs.add(cond_id)
                    ws_manager.register_cnsr(cond_id, self._process_tick)
            
            target_chat = chat_id or getattr(session, "chat_id", None)
            msg = f"✅ 실시간 조건검색 자동매매 감시를 시작합니다. (대상 조건식: {len(self.registered_seqs)}개)"
            logger.info(msg)
            
            if target_chat:
                from telegram.bot import reply_message
                reply_message(target_chat, msg)
                
            return ""

    def stop(self, keep_active_setting=False) -> str:
        with self.lock:
            if not self.active:
                return "⚠️ 조건검색 자동매매가 현재 실행 중이지 않습니다."
            
            self.active = False
            if not keep_active_setting:
                set_setting("jggs_active", False)
            
            from realtime.websocket_manager import WebsocketManager
            ws_manager = WebsocketManager()
            
            for cond_id in self.registered_seqs:
                ws_manager.unregister_cnsr(cond_id, self._process_tick)
                
            self.registered_seqs.clear()
            msg = "🛑 실시간 조건검색 자동매매 감시를 중단했습니다."
            logger.info(msg)
            return msg

    def _process_tick(self, tick):
        if not self.active or not is_market_open():
            return
            
        values = tick.get("values", {})
        cond_id = str(values.get("841", ""))
        stk_cd = tick.get("item") or values.get("9001")
        status = values.get("843")
        
        # 'I' (편입) 상태일 때만 명령어 실행
        if status != "I":
            return
            
        if not cond_id or not stk_cd:
            return
            
        # 명령어 실행 요청을 큐에 삽입
        self.cmd_queue.put((cond_id, stk_cd))
        logger.info(f"조건식 {cond_id} 종목 편입({stk_cd}) 감지. 실행 큐에 삽입 완료.")
        
    def _command_worker(self):
        logger.info("JGGS 명령어 실행 워커 스레드가 작동하기 시작했습니다.")
        while self.active:
            try:
                try:
                    # 1초 타임아웃으로 블록을 해제하여 active 플래그 체크 가능케 함
                    cond_id, stk_cd = self.cmd_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # 명령어 실행
                self._execute_mapped_commands(cond_id, stk_cd)
                self.cmd_queue.task_done()
                
                # 키움증권 오픈API 초당 제한(TR 호출 약 5건/초) 우회를 위해 0.25초 대기
                time.sleep(0.25)
            except Exception as e:
                logger.error(f"JGGS 워커 스레드 루프 중 오류 발생: {e}")
                time.sleep(1.0)
        
    def _execute_mapped_commands(self, cond_id, stk_cd):
        commands = load_jggs_commands()
        target_chat = getattr(session, "chat_id", None)
        if not target_chat:
            from config.config import telegram_chat_id
            target_chat = telegram_chat_id
        
        from telegram.bot import reply_message
        from telegram.commands import dispatch_command
        
        # 현재 조건식 번호에 매핑된 모든 명령어를 찾아 실행
        matched_cmds = [item['command'] for item in commands if str(item['cond_id']) == cond_id]
        
        for cmd_template in matched_cmds:
            # 괄호 '()' 를 종목코드로 치환
            actual_cmd = cmd_template.replace("()", stk_cd)
            logger.info(f"조건식 {cond_id} 종목 편입({stk_cd}) 발생. 치환된 명령어 실행: {actual_cmd}")
            
            if target_chat:
                reply_message(target_chat, f"🔔 [JGGS 편입 포착]\n종목코드: {stk_cd}\n조건식: {cond_id}\n명령어 실행: {actual_cmd}")
                
            try:
                # 텔레그램 명령어 디스패처를 통해 실행 (내부 API 호출)
                result = dispatch_command(actual_cmd, chat_id=target_chat)
                logger.info(f"JGGS 명령어({actual_cmd}) 실행 결과: {result}")
                if target_chat:
                    reply_message(target_chat, f"✅ [JGGS 실행 결과]\n{result}")
            except Exception as e:
                logger.error(f"JGGS 명령어({actual_cmd}) 실행 중 예외 발생: {e}")
                if target_chat:
                    reply_message(target_chat, f"❌ [JGGS 실행 오류]\n명령어: {actual_cmd}\n오류: {e}")
