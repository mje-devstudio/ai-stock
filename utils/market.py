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


def get_tick_size_for_down(price: int) -> int:
    """
    KRX 호가 하향 단위 계산 (2023년 1월 25일 개정 기준)
    호가를 낮출 때 적용될 틱 사이즈를 반환합니다.
    """
    if price <= 2000:
        return 1
    elif price <= 5000:
        return 5
    elif price <= 20000:
        return 10
    elif price <= 50000:
        return 50
    elif price <= 200000:
        return 100
    elif price <= 500000:
        return 500
    else:
        return 1000


def align_price_down(price: int) -> int:
    """
    주어진 가격을 KRX 호가 단위 그리드에 맞춰 하향 보정합니다.
    """
    if price < 2000:
        return price
    elif price < 5000:
        return 2000 + ((price - 2000) // 5) * 5
    elif price < 20000:
        return 5000 + ((price - 5000) // 10) * 10
    elif price < 50000:
        return 20000 + ((price - 20000) // 50) * 50
    elif price < 200000:
        return 50000 + ((price - 50000) // 100) * 100
    elif price < 500000:
        return 200000 + ((price - 200000) // 500) * 500
    else:
        return 500000 + ((price - 500000) // 1000) * 1000


def get_price_down_by_ticks(price: int, ticks: int) -> int:
    """
    주어진 가격에서 지정된 틱 수만큼 낮춘 가격을 반환합니다.
    시작 전 가격을 호가 단위 그리드에 맞춰 정렬합니다.
    """
    current_price = align_price_down(price)
    for _ in range(ticks):
        tick_size = get_tick_size_for_down(current_price)
        current_price -= tick_size
        if current_price <= 0:
            return 0
    return current_price


