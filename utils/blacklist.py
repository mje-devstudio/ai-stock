import os
import json
import threading
import logging
from utils.stock_code import clean_stock_code

logger = logging.getLogger(__name__)
BLACKLIST_FILE = os.path.join("config", "data", "blacklist.json")

class BlacklistManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(BlacklistManager, cls).__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        self.lock = threading.Lock()
        self.blacklist = []  # list of stock codes (clean 6-digit strings)
        self._load_blacklist()

    def _load_blacklist(self):
        try:
            if os.path.exists(BLACKLIST_FILE):
                with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
                    self.blacklist = json.load(f)
            else:
                self.blacklist = []
        except Exception as e:
            logger.error(f"[BlacklistManager] 파일 로드 실패: {e}")
            self.blacklist = []

    def _save_blacklist(self):
        try:
            os.makedirs(os.path.dirname(BLACKLIST_FILE), exist_ok=True)
            with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
                json.dump(self.blacklist, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[BlacklistManager] 파일 저장 실패: {e}")

    def add(self, stk_cd: str) -> tuple:
        """종목을 블랙리스트에 추가합니다. (is_success, msg)"""
        stk_cd = clean_stock_code(stk_cd)
        if len(stk_cd) != 6 or not stk_cd.isdigit():
            return False, "종목코드는 6자리 숫자여야 합니다."
            
        with self.lock:
            if stk_cd in self.blacklist:
                return False, f"이미 블랙리스트에 등록된 종목입니다: {stk_cd}"
            self.blacklist.append(stk_cd)
            self._save_blacklist()
            return True, f"블랙리스트에 종목이 추가되었습니다: {stk_cd}"

    def remove_by_index(self, index: int) -> tuple:
        """일련번호(1부터 시작)로 블랙리스트 항목을 삭제합니다. (is_success, msg)"""
        with self.lock:
            if index < 1 or index > len(self.blacklist):
                return False, f"올바르지 않은 일련번호입니다. (현재 등록 개수: {len(self.blacklist)}개)"
            removed = self.blacklist.pop(index - 1)
            self._save_blacklist()
            return True, f"블랙리스트에서 종목 {removed}이(가) 삭제되었습니다."

    def list(self) -> list:
        """블랙리스트 목록을 반환합니다."""
        with self.lock:
            return list(self.blacklist)

    def is_blacklisted(self, stk_cd: str) -> bool:
        """해당 종목이 블랙리스트에 등록되어 있는지 여부를 반환합니다."""
        stk_cd = clean_stock_code(stk_cd)
        with self.lock:
            return stk_cd in self.blacklist
