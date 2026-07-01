import logging
from utils.settings import set_setting

def trst_command(args: list, chat_id: str = None) -> str:
    """트레일링 스탑 파라미터를 설정합니다.

    사용법: trst {고점 대비 하락율} {최소 발동 수익률}
    예: trst 3.5 5
    """
    if len(args) < 2:
        return (
            "사용법이 올바르지 않습니다.\n"
            "사용법: trst {고점 대비 하락율} {최소 발동 수익률}\n"
            "예: trst 3.5 5"
        )

    try:
        drop_ratio = float(args[0])
    except ValueError:
        return f"고점 대비 하락율 형식이 올바르지 않습니다: {args[0]}\n숫자로 입력해주세요."

    try:
        min_profit = float(args[1])
    except ValueError:
        return f"최소 발동 수익률 형식이 올바르지 않습니다: {args[1]}\n숫자로 입력해주세요."

    drop_ratio = abs(drop_ratio)
    min_profit = abs(min_profit)

    ok1 = set_setting("trailing_stop_drop_ratio", drop_ratio)
    ok2 = set_setting("trailing_stop_min_profit", min_profit)

    if ok1 and ok2:
        logging.info(f"트레일링 스탑 설정: 하락율={drop_ratio}%, 최소 발동 수익률={min_profit}%")
        return (
            f"✅ 트레일링 스탑 설정이 완료되었습니다.\n"
            f"• 고점 대비 하락율: {drop_ratio}%\n"
            f"• 최소 발동 수익률: {min_profit}%"
        )
    else:
        return "❌ 트레일링 스탑 설정 저장 중 오류가 발생했습니다."
