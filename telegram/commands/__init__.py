from telegram.commands.login import login_command
from telegram.commands.power_off import power_off_command
from telegram.commands.search import search_command
from telegram.commands.buy import buy_command
from telegram.commands.report import report_command
from telegram.commands.sell import sell_command
from telegram.commands.mkhr import mkhr_command
from telegram.commands.stts import stts_command
from telegram.commands.rsv import rsv_command
from telegram.commands.help import help_command
from telegram.commands.tpr import tpr_command
from telegram.commands.slr import slr_command
from telegram.commands.stls import start_command, stop_command
from telegram.commands.rank import rank_command
from telegram.commands.gdcrs import gdcrs_command

# 명령어 등록 매핑
COMMANDS = {
    "login": login_command,
    "power": power_off_command,
    "poweroff": power_off_command,
    "srch": search_command,
    "buy": buy_command,
    "report": report_command,
    "r": report_command,
    "sell": sell_command,
    "mkhr": mkhr_command,
    "stts": stts_command,
    "rsv": rsv_command,
    "help": help_command,
    "h": help_command,
    "tpr": tpr_command,
    "slr": slr_command,
    "start": start_command,
    "stop": stop_command,
    "rank": rank_command,
    "rnk": rank_command,
    "gdcrs": gdcrs_command
}

def dispatch_command(message_text: str, chat_id: str = None) -> str:
    """
    메시지 텍스트를 파싱하여 알맞은 명령어로 라우팅합니다.
    명령어와 파라미터는 공백으로 구분되며, 대소문자를 구분하지 않습니다.
    """
    cleaned_text = message_text.strip()
    if not cleaned_text:
        return "명령어를 입력해주세요."
    
    parts = cleaned_text.split()
    cmd = parts[0].lower()
    if cmd.startswith('/'):
        cmd = cmd[1:]
    args = parts[1:]
    
    handler = COMMANDS.get(cmd)
    if handler:
        try:
            return handler(args, chat_id=chat_id)
        except Exception as e:
            return f"명령어 처리 중 내부 오류가 발생했습니다: {str(e)}"
    else:
        # 등록되지 않은 명령어 처리
        available_cmds = ", ".join(COMMANDS.keys())
        return f"알 수 없는 명령어입니다: {cmd}\n사용 가능한 명령어: {available_cmds}"
