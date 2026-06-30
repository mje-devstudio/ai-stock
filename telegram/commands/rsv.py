import logging
from utils.reservations import parse_time, load_reservations, add_reservation, remove_reservation, remove_all_reservations

def rsv_command(args: list, chat_id: str = None) -> str:
    """텔레그램 명령을 예약하고 관리하는 명령어입니다.
    
    사용법:
      1. 예약 추가: rsv {시간} {명령어} (예: rsv 10:00 buy 005930 5)
      2. 일회성 예약 추가: rsv once {시간} {명령어} (예: rsv once 10:00 buy 005930 5)
      3. 예약 조회: rsv list
      4. 예약 삭제: rsv remove {일련번호} (예: rsv remove 1)
      5. 전체 예약 삭제: rsv remove all
    """
    if not args:
        return (
            "사용법이 올바르지 않습니다.\n"
            "• 예약 추가: rsv {시간} {명령어} (예: rsv 10:00 buy 005930 5)\n"
            "• 일회성 예약 추가: rsv once {시간} {명령어} (예: rsv once 10:00 buy 005930 5)\n"
            "• 예약 조회: rsv list\n"
            "• 예약 삭제: rsv remove {일련번호} (예: rsv remove 1)\n"
            "• 전체 예약 삭제: rsv remove all"
        )
        
    sub_cmd = args[0].lower()
    
    if sub_cmd == "list":
        reservations = load_reservations()
        if not reservations:
            return "📋 등록된 예약 명령이 없습니다."
            
        msg_lines = [
            "📋 예약 명령 목록",
            "━━━━━━━━━━━━━━━━━━━"
        ]
        for rsv in reservations:
            once_suffix = " (1회성)" if rsv.get("once") else ""
            msg_lines.append(f"[{rsv['id']}] {rsv['time']} - {rsv['command']}{once_suffix}")
        msg_lines.append("━━━━━━━━━━━━━━━━━━━")
        return "\n".join(msg_lines)
        
    elif sub_cmd == "remove":
        if len(args) < 2:
            return "삭제할 예약의 일련번호를 입력해주세요. (예: rsv remove 1) 또는 전체 삭제 시 rsv remove all을 입력해주세요."
            
        target = args[1].lower()
        if target == "all":
            remove_all_reservations()
            return "✅ 모든 예약 명령이 삭제되었습니다."
            
        try:
            rsv_id = int(args[1])
        except ValueError:
            return f"일련번호 형식이 올바르지 않습니다: {args[1]}"
            
        success = remove_reservation(rsv_id)
        if success:
            return f"✅ 일련번호 {rsv_id}번 예약이 삭제되었습니다."
        else:
            return f"❌ 일련번호 {rsv_id}번 예약을 찾을 수 없습니다."
            
    elif sub_cmd == "once":
        if len(args) < 2:
            return "사용법: rsv once {시간} {명령어} (예: rsv once 10:00 buy 005930 5)"
            
        time_raw = args[1]
        time_parsed = parse_time(time_raw)
        if not time_parsed:
            return f"예약 시간 형식이 올바르지 않습니다: {time_raw}\n24시간제(예: 10:00 또는 09:30)로 입력해주세요."
            
        if len(args) < 3:
            return "예약할 명령어를 입력해주세요. (예: rsv once 10:00 buy 005930 5)"
            
        # 명령어 재조합 (예: ['buy', '005930', '5'] -> "buy 005930 5")
        command_str = " ".join(args[2:])
        
        # 예약할 명령 유효성 검사
        from telegram.commands import COMMANDS
        cmd_parts = command_str.strip().split()
        if not cmd_parts:
            return "예약할 명령어가 빈 값입니다."
            
        target_cmd = cmd_parts[0].lower()
        if target_cmd not in COMMANDS:
            available_cmds = ", ".join(COMMANDS.keys())
            return f"❌ 예약할 수 없는 명령어입니다: {target_cmd}\n사용 가능한 명령어: {available_cmds}"
            
        if target_cmd == "rsv":
            return "❌ 예약 명령(rsv) 자체는 예약할 수 없습니다."
            
        # 예약 저장
        new_rsv = add_reservation(time_parsed, command_str, once=True)
        logging.info(f"일회성 명령 예약 성공: ID={new_rsv['id']}, 시간={time_parsed}, 명령='{command_str}'")
        return (
            f"✅ 일회성 명령어가 성공적으로 예약되었습니다.\n"
            f"- 일련번호: {new_rsv['id']}\n"
            f"- 실행 시간: {time_parsed} (1회 실행)\n"
            f"- 예약 명령: {command_str}"
        )
        
    else:
        # 예약 추가 패턴: rsv {시간} {명령어}
        time_raw = args[0]
        time_parsed = parse_time(time_raw)
        if not time_parsed:
            return f"예약 시간 형식이 올바르지 않습니다: {time_raw}\n24시간제(예: 10:00 또는 09:30)로 입력해주세요."
            
        if len(args) < 2:
            return "예약할 명령어를 입력해주세요. (예: rsv 10:00 buy 005930 5)"
            
        # 명령어 재조합 (예: ['buy', '005930', '5'] -> "buy 005930 5")
        command_str = " ".join(args[1:])
        
        # 예약할 명령이 올바른지 최소한의 유효성 검사 (첫 단어가 등록된 명령어인지 검사)
        from telegram.commands import COMMANDS
        cmd_parts = command_str.strip().split()
        if not cmd_parts:
            return "예약할 명령어가 빈 값입니다."
            
        target_cmd = cmd_parts[0].lower()
        if target_cmd not in COMMANDS:
            available_cmds = ", ".join(COMMANDS.keys())
            return f"❌ 예약할 수 없는 명령어입니다: {target_cmd}\n사용 가능한 명령어: {available_cmds}"
            
        if target_cmd == "rsv":
            return "❌ 예약 명령(rsv) 자체는 예약할 수 없습니다."
            
        # 예약 저장
        new_rsv = add_reservation(time_parsed, command_str, once=False)
        logging.info(f"명령 예약 성공: ID={new_rsv['id']}, 시간={time_parsed}, 명령='{command_str}'")
        return (
            f"✅ 명령어가 성공적으로 예약되었습니다.\n"
            f"- 일련번호: {new_rsv['id']}\n"
            f"- 실행 시간: {time_parsed} (주말 제외 매일)\n"
            f"- 예약 명령: {command_str}"
        )
