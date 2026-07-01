from utils.jggs import add_jggs_command, load_jggs_commands, remove_jggs_command_by_index, clear_jggs_commands

def jggs_command(args: list, chat_id: str = None) -> str:
    """조건검색식에 명령어를 배정하고 관리하는 명령어입니다.

    사용법:
      1. 명령어 배정: jggs add {조건식번호} {명령어} (예: jggs add 0 buy () max 100000)
      2. 배정 목록 조회: jggs list
      3. 배정 삭제: jggs remove {일련번호} (예: jggs remove 1)
      4. 배정 전체 비우기: jggs clear
      5. 실시간 조건검색 수신 테스트: jggs test
    """
    if not args:
        return (
            "사용법이 올바르지 않습니다.\n"
            "• 명령어 배정: jggs add {조건식번호} {명령어} (예: jggs add 0 buy () max 100000)\n"
            "• 목록 조회: jggs list\n"
            "• 배정 삭제: jggs remove {일련번호} (예: jggs remove 1)\n"
            "• 전체 비우기: jggs clear\n"
            "• 수신 테스트: jggs test"
        )

    sub_cmd = args[0].lower()

    if sub_cmd == "add":
        if len(args) < 3:
            return "사용법: jggs add {조건식번호} {명령어}\n예: jggs add 0 buy () max 100000"

        cond_id = args[1].strip()
        command_str = " ".join(args[2:]).strip()

        # 명령어 존재 여부 및 유효성 확인
        from telegram.commands import COMMANDS
        cmd_parts = command_str.split()
        if not cmd_parts:
            return "배정할 명령어가 빈 값입니다."

        target_cmd = cmd_parts[0].lower()
        if target_cmd not in COMMANDS:
            available_cmds = ", ".join(COMMANDS.keys())
            return f"❌ 배정할 수 없는 명령어입니다: {target_cmd}\n사용 가능한 명령어: {available_cmds}"

        if target_cmd == "jggs":
            return "❌ 조건식 배정 명령어(jggs) 자체는 배정할 수 없습니다."

        success = add_jggs_command(cond_id, command_str)
        if success:
            return (
                f"✅ 조건식 명령 배정 완료\n"
                f"- 조건식번호: {cond_id}\n"
                f"- 명령어: {command_str}"
            )
        else:
            return "❌ 명령 배정 중 오류가 발생했습니다."

    elif sub_cmd == "list":
        commands = load_jggs_commands()
        if not commands:
            return "📋 등록된 조건식 배정 명령이 없습니다."

        msg_lines = [
            "📋 조건식 배정 명령어 목록",
            "━━━━━━━━━━━━━━━━━━━"
        ]
        # 목록의 일련번호는 조회시마다 1번부터 매김
        for idx, item in enumerate(commands, 1):
            msg_lines.append(f"[{idx}] 조건식 {item['cond_id']} : {item['command']}")
        msg_lines.append("━━━━━━━━━━━━━━━━━━━")
        return "\n".join(msg_lines)

    elif sub_cmd == "remove":
        if len(args) < 2:
            return "삭제할 배정 명령어의 일련번호를 입력해주세요. (예: jggs remove 1)"

        try:
            index = int(args[1])
        except ValueError:
            return f"일련번호 형식이 올바르지 않습니다: {args[1]}"

        if index < 1:
            return "❌ 일련번호는 1부터 시작합니다. `jggs list` 명령어로 삭제할 일련번호를 확인해주세요."

        success, removed = remove_jggs_command_by_index(index)
        if success and removed:
            return (
                f"✅ 일련번호 {index}번 배정 명령이 삭제되었습니다.\n"
                f"- 조건식번호: {removed['cond_id']}\n"
                f"- 명령어: {removed['command']}"
            )
        else:
            return f"❌ 일련번호 {index}번 배정 명령을 찾을 수 없거나 삭제에 실패했습니다."

    elif sub_cmd == "clear":
        success = clear_jggs_commands()
        if success:
            return "✅ 조건식 배정 명령어 목록이 모두 비워졌습니다."
        else:
            return "❌ 목록 비우기 중 오류가 발생했습니다."

    elif sub_cmd == "test":
        commands = load_jggs_commands()
        if not commands:
            return "📋 등록된 조건식 배정 명령이 없습니다. 먼저 `jggs add`로 명령을 등록해주세요."
            
        from realtime.websocket_manager import WebsocketManager
        import logging
        
        ws_manager = WebsocketManager()
        ws_manager.start()
        
        logger = logging.getLogger(__name__)
        
        def make_test_callback(cond_id, command_str):
            def test_callback(tick):
                # tick values: {'841': 'seq', '9001': 'code', '843': 'I' or 'D', ...}
                values = tick.get("values", {})
                stk_cd = tick.get("item") or values.get("9001")
                status = values.get("843")
                status_str = "진입(I)" if status == "I" else "이탈(D)" if status == "D" else status
                msg = f"[조건검색 실시간 테스트] seq: {cond_id}, 종목코드: {stk_cd}, 상태: {status_str}, 연결된 명령: {command_str}"
                print(msg)
                logger.info(msg)
            return test_callback
            
        registered_seqs = set()
        for item in commands:
            cond_id = item['cond_id']
            if cond_id not in registered_seqs:
                registered_seqs.add(cond_id)
                cb = make_test_callback(cond_id, item['command'])
                ws_manager.register_cnsr(cond_id, cb)
                
        return f"✅ {len(registered_seqs)}개의 조건식에 대한 실시간 수신 테스트를 시작합니다. 터미널 로그를 확인해주세요."

    else:
        return (
            f"올바르지 않은 하위 명령입니다: {sub_cmd}\n"
            "사용 가능한 명령어:\n"
            "• jggs add {조건식번호} {명령어}\n"
            "• jggs list\n"
            "• jggs remove {일련번호}\n"
            "• jggs clear\n"
            "• jggs test"
        )
