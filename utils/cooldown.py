import os
import json
import time
import threading
import logging
from utils.settings import get_setting

logger = logging.getLogger(__name__)
COOLDOWN_FILE = os.path.join("config", "data", "cooldowns.json")

class CooldownManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CooldownManager, cls).__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        self.lock = threading.Lock()
        self.cooldowns = {}  # { stk_cd: float(timestamp_of_last_sell) }
        self._load_cooldowns()

    def _load_cooldowns(self):
        try:
            if os.path.exists(COOLDOWN_FILE):
                with open(COOLDOWN_FILE, "r", encoding="utf-8") as f:
                    self.cooldowns = json.load(f)
            else:
                self.cooldowns = {}
        except Exception as e:
            logger.error(f"[CooldownManager] 파일 로드 실패: {e}")
            self.cooldowns = {}

    def _save_cooldowns(self):
        try:
            os.makedirs(os.path.dirname(COOLDOWN_FILE), exist_ok=True)
            with open(COOLDOWN_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cooldowns, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[CooldownManager] 파일 저장 실패: {e}")

    def record_sell(self, stk_cd: str):
        """매도 완료 시간(현재 타임스탬프)을 기록합니다."""
        with self.lock:
            self.cooldowns[stk_cd] = time.time()
            self._save_cooldowns()
            logger.info(f"[CooldownManager] 종목 {stk_cd} 매도 완료 시간 기록됨")

    def is_in_cooldown(self, stk_cd: str) -> tuple:
        """
        해당 종목이 쿨다운 감시 상태(매수 불가)인지 여부를 반환합니다.
        반환값: (is_cooldown: bool, remaining_seconds: float)
        """
        try:
            cooldown_hours = float(get_setting("cooldown_hours", 0.0))
        except (ValueError, TypeError):
            cooldown_hours = 0.0

        if cooldown_hours <= 0.0:
            return False, 0.0

        with self.lock:
            last_sell = self.cooldowns.get(stk_cd)
            if not last_sell:
                return False, 0.0

            elapsed = time.time() - last_sell
            limit_seconds = cooldown_hours * 3600.0
            
            if elapsed < limit_seconds:
                remaining = limit_seconds - elapsed
                return True, remaining
            else:
                # 쿨다운 만료됨 -> 목록에서 제거하여 정리
                del self.cooldowns[stk_cd]
                self._save_cooldowns()
                return False, 0.0
