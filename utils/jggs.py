import os
import json
import logging

JGGS_FILE = os.path.join("config", "data", "jggs_commands.json")

def load_jggs_commands() -> list:
    """조건검색식 배정 명령 목록을 로드합니다. 파일이 없으면 빈 목록을 반환합니다."""
    if not os.path.exists(JGGS_FILE):
        return []
    try:
        with open(JGGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"jggs 파일 로드 중 오류 발생: {e}")
        return []

def save_jggs_commands(commands: list) -> bool:
    """조건검색식 배정 명령 목록을 파일에 저장합니다."""
    try:
        dir_name = os.path.dirname(JGGS_FILE)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        with open(JGGS_FILE, "w", encoding="utf-8") as f:
            json.dump(commands, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"jggs 파일 저장 중 오류 발생: {e}")
        return False

def add_jggs_command(cond_id: str, command: str) -> bool:
    """조건검색식에 명령어를 추가합니다."""
    commands = load_jggs_commands()
    commands.append({
        "cond_id": cond_id,
        "command": command
    })
    return save_jggs_commands(commands)

def remove_jggs_command_by_index(index: int) -> tuple:
    """1-based index로 지정된 명령을 삭제합니다. (성공 여부, 삭제된 항목 정보)"""
    commands = load_jggs_commands()
    if index < 1 or index > len(commands):
        return False, None
    removed = commands.pop(index - 1)
    success = save_jggs_commands(commands)
    return success, removed

def clear_jggs_commands() -> bool:
    """모든 조건검색식 명령 목록을 삭제합니다."""
    return save_jggs_commands([])
