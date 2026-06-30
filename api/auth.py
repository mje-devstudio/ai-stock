import requests
from config.config import (
    paper_host_url,
    paper_app_key,
    paper_app_secret,
    real_host_url,
    real_app_key,
    real_app_secret,
)

def request_access_token(mode: str) -> dict:
    """
    지정된 모드("paper" 또는 "real")에 맞춰 키움증권 REST API 접근 토큰 발급을 요청합니다.
    
    반환 값 형식:
    {
        "success": bool,
        "token": str or None,
        "host_url": str,
        "error_msg": str or None
    }
    """
    if mode == "paper":
        host = paper_host_url
        app_key = paper_app_key
        app_secret = paper_app_secret
    elif mode == "real":
        host = real_host_url
        app_key = real_app_key
        app_secret = real_app_secret
    else:
        return {
            "success": False,
            "token": None,
            "host_url": "",
            "error_msg": f"알 수 없는 로그인 모드: {mode}"
        }

    url = f"{host}/oauth2/token"
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
    }
    data = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "secretkey": app_secret,
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            res_data = response.json()
            # token 필드가 있는지 확인 (기존 main.py에서는 paper_body.get("token", "") 사용)
            token = res_data.get("token") or res_data.get("access_token")
            if token:
                return {
                    "success": True,
                    "token": token,
                    "host_url": host,
                    "error_msg": None
                }
            else:
                return {
                    "success": False,
                    "token": None,
                    "host_url": host,
                    "error_msg": f"응답에 토큰 정보가 없습니다. (Response: {res_data})"
                }
        else:
            return {
                "success": False,
                "token": None,
                "host_url": host,
                "error_msg": f"HTTP {response.status_code}: {response.text}"
            }
    except Exception as e:
        return {
            "success": False,
            "token": None,
            "host_url": host,
            "error_msg": f"네트워크 오류 또는 예외 발생: {str(e)}"
        }
