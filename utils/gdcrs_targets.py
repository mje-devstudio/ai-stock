import os
import json
import logging

GDCRS_TARGETS_FILE = os.path.join("config", "data", "gdcrs_targets.json")

def load_gdcrs_targets() -> list:
    """골든크로스 감시 대상 종목 목록을 로드합니다."""
    if not os.path.exists(GDCRS_TARGETS_FILE):
        return []
    try:
        with open(GDCRS_TARGETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"gdcrs 대상 파일 로드 중 오류 발생: {e}")
        return []

def save_gdcrs_targets(targets: list) -> bool:
    """골든크로스 감시 대상 종목 목록을 파일에 저장합니다."""
    try:
        dir_name = os.path.dirname(GDCRS_TARGETS_FILE)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        with open(GDCRS_TARGETS_FILE, "w", encoding="utf-8") as f:
            json.dump(targets, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"gdcrs 대상 파일 저장 중 오류 발생: {e}")
        return False

def add_gdcrs_target(stk_cd: str, amount: int) -> bool:
    """골든크로스 감시 대상 종목을 추가합니다. 동일 종목 존재 시 금액만 갱신합니다."""
    targets = load_gdcrs_targets()
    for target in targets:
        if target["stk_cd"] == stk_cd:
            target["amount"] = amount
            return save_gdcrs_targets(targets)
            
    targets.append({
        "stk_cd": stk_cd,
        "amount": amount
    })
    return save_gdcrs_targets(targets)

def remove_gdcrs_target_by_index(index: int) -> tuple:
    """1-based index로 지정된 감시 대상 종목을 삭제합니다. (성공 여부, 삭제된 항목 정보)"""
    targets = load_gdcrs_targets()
    if index < 1 or index > len(targets):
        return False, None
    removed = targets.pop(index - 1)
    success = save_gdcrs_targets(targets)
    return success, removed


def clear_gdcrs_targets() -> bool:
    """골든크로스 감시 대상 종목 목록을 모두 삭제합니다."""
    return save_gdcrs_targets([])

