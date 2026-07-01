import os
import json

SETTINGS_DIR = os.path.join("config", "data")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")
DEFAULT_SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings-default.json")

DEFAULT_SETTINGS = {
    "renewal_time": "08:55",
    "market_start_time": "09:00",
    "market_end_time": "15:30",
    "take_profit_ratio": 4.0,
    "stop_loss_ratio": -3.0,
    "gdcrs_short": 5,
    "gdcrs_long": 20,
    "ddcrs_short": 5,
    "ddcrs_long": 20,
    "gdcrs_active": False,
    "ddcrs_active": False,
    "stls_active": False,
    "trailing_stop_drop_ratio": 3.0,
    "trailing_stop_min_profit": 5.0,
    "order_timeout_seconds": 0,
    "order_timeout_action": "cancel",
    "cooldown_hours": 0.0,
    "max_holdings": 0
}


def init_settings():
    """설정 디렉토리와 파일을 초기화합니다."""
    if not os.path.exists(SETTINGS_DIR):
        os.makedirs(SETTINGS_DIR)
    # 기본값 파일 생성
    if not os.path.exists(DEFAULT_SETTINGS_FILE):
        try:
            with open(DEFAULT_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_SETTINGS, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"settings-default.json 생성 실패: {e}")
    # 사용자 설정 파일 생성 (없으면 기본값 복사)
    if not os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_SETTINGS, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"settings.json 생성 실패: {e}")

def set_setting(key: str, value) -> bool:
    """설정 값을 저장합니다. 기존 파일이 있으면 업데이트하고 없으면 생성합니다."""
    init_settings()
    try:
        data = {}
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        data[key] = value
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"설정 저장 오류 (Key: {key}): {e}")
        return False

def get_setting(key: str, default=None):
    """설정 값을 가져옵니다. 키가 없으면 기본값을 반환합니다."""
    init_settings()
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get(key, default if default is not None else DEFAULT_SETTINGS.get(key))
    except Exception as e:
        print(f"설정 읽기 오류 (Key: {key}): {e}")
    return default if default is not None else DEFAULT_SETTINGS.get(key)

def get_all_settings() -> dict:
    """모든 설정 값을 가져옵니다. 기본값과 사용자 설정을 병합하여 반환합니다."""
    init_settings()
    try:
        data = {}
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        merged = DEFAULT_SETTINGS.copy()
        merged.update(data)
        return merged
    except Exception as e:
        print(f"설정 읽기 오류: {e}")
        return DEFAULT_SETTINGS.copy()

def reset_to_default_settings() -> bool:
    """모든 설정을 기본값으로 초기화합니다."""
    init_settings()
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"설정 초기화 오류: {e}")
        return False
