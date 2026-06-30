import logging
from utils.settings import set_setting

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

def mkhr_command(args: list, chat_id: str = None) -> str:
    """주식시장 거래시간(장 시간)을 설정하는 명령어입니다.
    
    사용법: mkhr {시작시간} {종료시간}
    예: mkhr 9:30 15:00
    """
    if len(args) < 2:
        return "사용법이 올바르지 않습니다.\n사용법: mkhr {시작시간} {종료시간}\n예: mkhr 9:30 15:00"
    
    start_raw = args[0]
    end_raw = args[1]
    
    start_time = parse_time(start_raw)
    if not start_time:
        return f"시작 시간 형식이 올바르지 않습니다: {start_raw}\n24시간제(예: 9:30 또는 09:30)로 입력해주세요."
        
    end_time = parse_time(end_raw)
    if not end_time:
        return f"종료 시간 형식이 올바르지 않습니다: {end_raw}\n24시간제(예: 15:00)로 입력해주세요."
        
    if start_time >= end_time:
        return f"시간 설정 오류: 시작 시간({start_time})은 종료 시간({end_time})보다 빨라야 합니다."
        
    # 설정 저장
    success_start = set_setting("market_start_time", start_time)
    success_end = set_setting("market_end_time", end_time)
    
    if success_start and success_end:
        logging.info(f"장 시간이 성공적으로 설정되었습니다: {start_time} ~ {end_time}")
        return f"✅ 장 시간 설정이 완료되었습니다.\n- 시작 시간: {start_time}\n- 종료 시간: {end_time}"
    else:
        logging.error("장 시간 설정 저장에 실패했습니다.")
        return "❌ 설정 저장 중 오류가 발생했습니다. 설정 파일 권한 등을 확인해주세요."
