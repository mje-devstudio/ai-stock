import datetime
from utils.settings import get_setting

def is_market_open() -> bool:
    """현재 시간이 설정된 장 시간(평일 장 시작 ~ 종료) 내에 있는지 확인합니다."""
    now = datetime.datetime.now()
    
    # 주말(토요일=5, 일요일=6) 제외
    if now.weekday() >= 5:
        return False
        
    start_str = get_setting("market_start_time") or "09:00"
    end_str = get_setting("market_end_time") or "15:30"
    
    current_time = now.strftime("%H:%M")
    return start_str <= current_time < end_str
