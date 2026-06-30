import logging
from utils.settings import set_setting

def slr_command(args: list, chat_id: str = None) -> str:
    """손절 기준 퍼센티지를 설정합니다. 입력값은 항상 음수 실수로 저장됩니다.
    
    사용법: slr {손절기준} (예: slr 3 또는 slr 3.5)
    """
    if not args:
        return "사용법이 올바르지 않습니다.\n사용법: slr {손절기준}\n예: slr 3 또는 slr 3.5"
        
    try:
        val = float(args[0])
    except ValueError:
        return f"손절 기준 형식이 올바르지 않습니다: {args[0]}\n숫자로 입력해주세요."
        
    slr_val = -abs(val)
    success = set_setting("stop_loss_ratio", slr_val)
    
    if success:
        logging.info(f"손절 기준이 설정되었습니다: {slr_val}%")
        return f"✅ 손절 기준이 {slr_val}%로 설정되었습니다."
    else:
        return "❌ 손절 기준 설정 저장 중 오류가 발생했습니다."
