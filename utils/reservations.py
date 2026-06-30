import os
import json
import logging

RESERVATIONS_FILE = os.path.join("config", "data", "reservations.json")

def parse_time(time_str: str) -> str:
    """시간 문자열(H:M 또는 HH:MM)을 파싱하여 HH:MM 형식의 문자열을 반환합니다.
    유효하지 않은 시간일 경우 None을 반환합니다.
    """
    try:
        parts = time_str.split(':')
        if len(parts) != 2:
            return None
        h = int(parts[0])
        m = int(parts[1])
        if 0 <= h < 24 and 0 <= m < 60:
            return f"{h:02d}:{m:02d}"
    except ValueError:
        pass
    return None

def load_reservations() -> list:
    """예약 목록을 파일에서 로드합니다. 파일이 없으면 빈 목록을 반환합니다."""
    if not os.path.exists(RESERVATIONS_FILE):
        return []
    try:
        with open(RESERVATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"예약 파일 로드 중 오류 발생: {e}")
        return []

def save_reservations(reservations: list) -> bool:
    """예약 목록을 파일에 저장합니다."""
    try:
        dir_name = os.path.dirname(RESERVATIONS_FILE)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        with open(RESERVATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(reservations, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"예약 파일 저장 중 오류 발생: {e}")
        return False

def add_reservation(time_str: str, command: str, once: bool = False) -> dict:
    """새로운 예약을 추가하고 저장합니다."""
    reservations = load_reservations()
    next_id = max([r["id"] for r in reservations], default=0) + 1
    new_rsv = {
        "id": next_id,
        "time": time_str,
        "command": command,
        "once": once,
        "last_run_date": ""
    }
    reservations.append(new_rsv)
    save_reservations(reservations)
    return new_rsv

def remove_reservation(rsv_id: int) -> bool:
    """일련번호에 해당하는 예약을 삭제합니다. 성공 시 True, 없으면 False를 반환합니다."""
    reservations = load_reservations()
    filtered = [r for r in reservations if r["id"] != rsv_id]
    if len(filtered) == len(reservations):
        return False
    save_reservations(filtered)
    return True

def remove_all_reservations() -> bool:
    """모든 예약을 삭제합니다."""
    return save_reservations([])
