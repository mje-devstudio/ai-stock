import requests
from api.session import session
from config.config import account_no, account_pwd
from utils.stock_code import clean_stock_code

def buy_stock(stk_cd: str, ord_qty: int, ord_pric: int = 0) -> dict:
    """
    주식 매수 주문을 전송합니다 (kt10000).
    ord_pric이 0이면 시장가(03), 0보다 크면 지정가(00)로 주문합니다.
    """
    stk_cd = clean_stock_code(stk_cd)
    if not session.is_logged_in():
        return {"success": False, "error_msg": "로그인이 필요합니다. 먼저 login [paper|real] 명령어를 실행하세요."}
    
    url = f"{session.host_url}/api/dostk/ordr"
    
    headers = {
        "api-id": "kt10000",
        "authorization": f"Bearer {session.token}",
        "Content-Type": "application/json;charset=UTF-8"
    }
    
    trde_tp = "0" if ord_pric > 0 else "3"
    ord_uv = str(ord_pric) if ord_pric > 0 else ""
    
    data = {
        "acc_no": account_no,
        "acc_pwd": account_pwd,
        "dmst_stex_tp": "KRX",
        "stk_cd": stk_cd,
        "ord_qty": str(ord_qty),
        "ord_uv": ord_uv,
        "trde_tp": trde_tp
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            res_data = response.json()
            return {"success": True, "data": res_data}
        else:
            return {"success": False, "error_msg": f"API 요청 실패 (HTTP {response.status_code}): {response.text}"}
    except Exception as e:
        return {"success": False, "error_msg": f"네트워크 오류 또는 예외 발생: {str(e)}"}


def sell_stock(stk_cd: str, ord_qty: int) -> dict:
    """
    시장가 매도 주문을 전송합니다 (kt10001).
    """
    stk_cd = clean_stock_code(stk_cd)
    if not session.is_logged_in():
        return {"success": False, "error_msg": "로그인이 필요합니다. 먼저 login [paper|real] 명령어를 실행하세요."}
    
    url = f"{session.host_url}/api/dostk/ordr"
    
    headers = {
        "api-id": "kt10001",
        "authorization": f"Bearer {session.token}",
        "Content-Type": "application/json;charset=UTF-8"
    }
    
    data = {
        "acc_no": account_no,
        "acc_pwd": account_pwd,
        "dmst_stex_tp": "KRX",
        "stk_cd": stk_cd,
        "ord_qty": str(ord_qty),
        "ord_uv": "",       # 시장가이므로 주문단가는 공백
        "trde_tp": "3",     # 3: 시장가
        "cond_uv": ""
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            res_data = response.json()
            return {"success": True, "data": res_data}
        else:
            return {"success": False, "error_msg": f"API 요청 실패 (HTTP {response.status_code}): {response.text}"}
    except Exception as e:
        return {"success": False, "error_msg": f"네트워크 오류 또는 예외 발생: {str(e)}"}
