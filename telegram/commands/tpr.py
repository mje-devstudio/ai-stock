import logging
from utils.settings import set_setting

def tpr_command(args: list, chat_id: str = None) -> str:
    """익절 기준 퍼센티지를 설정합니다. 입력값은 항상 양수 실수로 저장됩니다.
    
    사용법: tpr {익절기준} (예: tpr 4 또는 tpr 4.5)
    """
    if not args:
        return "사용법이 올바르지 않습니다.\n사용법: tpr {익절기준}\n예: tpr 4 또는 tpr 4.5"
        
    try:
        val = float(args[0])
    except ValueError:
        return f"익절 기준 형식이 올바르지 않습니다: {args[0]}\n숫자로 입력해주세요."
        
    tpr_val = abs(val)
    success = set_setting("take_profit_ratio", tpr_val)
    
    if success:
        logging.info(f"익절 기준이 설정되었습니다: {tpr_val}%")
        return f"✅ 익절 기준이 {tpr_val}%로 설정되었습니다."
    else:
        return "❌ 익절 기준 설정 저장 중 오류가 발생했습니다."
