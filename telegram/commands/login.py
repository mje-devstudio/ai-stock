from api.auth import request_access_token
from api.session import session
from utils.settings import set_setting
from utils.scheduler import send_notification

def login_command(args: list, chat_id: str = None) -> str:
    """
    'login' 명령어를 처리합니다.
    사용법:
    1. 로그인: login [paper|real]
    2. 자동 갱신 시간 변경: login renewal [HH:MM]
    """
    if not args:
        return (
            "올바른 명령어를 입력해주세요.\n"
            "사용법:\n"
            "- 로그인: login [paper|real]\n"
            "- 갱신시간 변경: login renewal [HH:MM] (예: login renewal 8:50)"
        )
    
    subcmd = args[0].lower()
    
    # 1. 자동 갱신 시간 설정 변경 처리
    if subcmd == "renewal":
        if len(args) < 2:
            return "갱신할 시간을 입력해주세요. (예: login renewal 8:50)"
        
        time_str = args[1].strip()
        # 시간 포맷(HH:MM) 파싱 및 유효성 검증
        try:
            parts = time_str.split(":")
            if len(parts) != 2:
                return "올바르지 않은 시간 형식입니다. HH:MM 형식으로 입력해주세요. (예: 8:50)"
            
            h = int(parts[0])
            m = int(parts[1])
            if not (0 <= h < 24 and 0 <= m < 60):
                return "시간 범위가 올바르지 않습니다. (시간: 0~23, 분: 0~59)"
            
            normalized_time = f"{h:02d}:{m:02d}"
            
            # 설정 저장
            if set_setting("renewal_time", normalized_time):
                return f"토큰 자동 갱신 시간이 `{normalized_time}`(24시간제)로 설정되었습니다."
            else:
                return "설정 저장 중 오류가 발생했습니다."
        except ValueError:
            return "올바르지 않은 시간 형식입니다. 숫자로 구성된 HH:MM 형식이어야 합니다. (예: 08:50)"

    # 2. 투자 환경 로그인 처리 (paper / real)
    if subcmd not in ["paper", "real"]:
        return (
            f"올바르지 않은 서브커맨드/모드입니다: {args[0]}\n"
            "사용법:\n"
            "- 로그인: login [paper|real]\n"
            "- 갱신시간 변경: login renewal [HH:MM]"
        )
    
    mode = subcmd
    mode_kr = "모의투자" if mode == "paper" else "실투자"
    
    # API 로그인 요청
    res = request_access_token(mode)
    
    if res["success"]:
        token = res["token"]
        host_url = res["host_url"]
        
        # 전역 세션 업데이트 (chat_id 포함)
        session.update(token=token, mode=mode, host_url=host_url, chat_id=chat_id)
        
        # 세션 모드에 따라 HTTP rate limit 조정
        from utils.http_queue import set_global_max
        mode_max = 4 if mode == "paper" else 16
        set_global_max(mode_max)
        
        # 텔레그램 및 터미널에 알림 전송
        send_notification(f"[{mode_kr}] 로그인 성공! 토큰이 발급되었습니다.")
        
        # 보안을 위해 토큰 앞뒤 일부만 노출
        masked_token = f"{token[:10]}...{token[-10:]}" if len(token) > 20 else token
        return (
            f"[{mode_kr}] 로그인 성공!\n"
            f"- 모드: {mode.upper()}\n"
            f"- 호스트: {host_url}\n"
            f"- 토큰: {masked_token}\n"
            f"- 알림 대상 Chat ID: {chat_id or '미지정'}\n"
            f"- HTTP 요청 한도: {mode_max}건/초"
        )
    else:
        error_msg = res["error_msg"]
        return f"[{mode_kr}] 로그인 실패\n- 사유: {error_msg}"
