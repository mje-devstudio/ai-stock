import requests
from api.session import session
from utils.stock_code import clean_stock_code

def get_stock_info(stk_cd: str) -> dict:
    """
    종목 코드를 입력하여 해당 국내주식 종목의 상세 정보를 단건으로 조회합니다.
    """
    stk_cd = clean_stock_code(stk_cd)
    if not session.is_logged_in():
        return {"success": False, "error_msg": "로그인이 필요합니다. 먼저 login [paper|real] 명령어를 실행하세요."}
    
    url = f"{session.host_url}/api/dostk/mrkcond"
    
    headers = {
        "api-id": "ka10007",
        "authorization": f"Bearer {session.token}",
        "Content-Type": "application/json;charset=UTF-8"
    }
    
    data = {
        "stk_cd": stk_cd
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


def get_account_evaluation() -> dict:
    """
    사용자 계좌의 예수금, 예탁자산평가액, 총매입금액, 누적손익 등의 자금현황과
    현재 계좌에 보유 중인 개별 종목들의 정보를 조회합니다 (kt00004).
    """
    if not session.is_logged_in():
        return {"success": False, "error_msg": "로그인이 필요합니다. 먼저 login [paper|real] 명령어를 실행하세요."}
    
    url = f"{session.host_url}/api/dostk/acnt"
    
    headers = {
        "api-id": "kt00004",
        "authorization": f"Bearer {session.token}",
        "Content-Type": "application/json;charset=UTF-8"
    }
    
    body = {
        "qry_tp": "0",
        "dmst_stex_tp": "KRX"
    }
    
    all_holdings = []
    account_info = {}
    
    cont_yn = "N"
    next_key = ""
    
    while True:
        req_headers = headers.copy()
        if cont_yn == "Y":
            req_headers["cont-yn"] = "Y"
            req_headers["next-key"] = next_key
            
        try:
            response = requests.post(url, headers=req_headers, json=body, timeout=10)
            
            if response.status_code != 200:
                return {"success": False, "error_msg": f"API 요청 실패 (HTTP {response.status_code}): {response.text}"}
                
            res_data = response.json()
            res_body = res_data.get("body", res_data)
            
            return_code = res_body.get("return_code")
            if return_code is not None and int(return_code) != 0:
                return {"success": False, "error_msg": f"API 오류: {res_body.get('return_msg', '알 수 없는 오류')}"}
                
            if not account_info:
                account_info = {
                    "acnt_nm": res_body.get("acnt_nm"),
                    "brch_nm": res_body.get("brch_nm"),
                    "entr": res_body.get("entr"),
                    "d2_entra": res_body.get("d2_entra"),
                    "tot_est_amt": res_body.get("tot_est_amt"),
                    "aset_evlt_amt": res_body.get("aset_evlt_amt"),
                    "tot_pur_amt": res_body.get("tot_pur_amt"),
                    "prsm_dpst_aset_amt": res_body.get("prsm_dpst_aset_amt"),
                    "lspft": res_body.get("lspft"),
                    "lspft_rt": res_body.get("lspft_rt"),
                    "tdy_lspft": res_body.get("tdy_lspft"),
                    "tdy_lspft_rt": res_body.get("tdy_lspft_rt"),
                }
                
            holdings = res_body.get("stk_acnt_evlt_prst", [])
            if holdings:
                for h in holdings:
                    if "stk_cd" in h:
                        h["stk_cd"] = clean_stock_code(h["stk_cd"])
                all_holdings.extend(holdings)
                
            res_headers = response.headers
            cont_yn = res_headers.get("cont-yn", "N")
            next_key = res_headers.get("next-key", "")
            
            if cont_yn != "Y" or not next_key:
                break
                
        except Exception as e:
            return {"success": False, "error_msg": f"네트워크 오류 또는 예외 발생: {str(e)}"}
            
    return {
        "success": True,
        "account_info": account_info,
        "holdings": all_holdings
    }


def get_daily_balance_ratio() -> dict:
    """
    사용자 계좌의 일별잔고수익률 정보를 조회합니다 (ka01690).
    """
    if not session.is_logged_in():
        return {"success": False, "error_msg": "로그인이 필요합니다. 먼저 login [paper|real] 명령어를 실행하세요."}
    
    import datetime
    today_str = datetime.datetime.now().strftime("%Y%m%d")
    
    url = f"{session.host_url}/api/dostk/acnt"
    
    headers = {
        "api-id": "ka01690",
        "authorization": f"Bearer {session.token}",
        "Content-Type": "application/json;charset=UTF-8"
    }
    
    body = {
        "qry_dt": today_str
    }
    
    all_holdings = []
    
    cont_yn = "N"
    next_key = ""
    
    while True:
        req_headers = headers.copy()
        if cont_yn == "Y":
            req_headers["cont-yn"] = "Y"
            req_headers["next-key"] = next_key
            
        try:
            response = requests.post(url, headers=req_headers, json=body, timeout=10)
            
            if response.status_code != 200:
                return {"success": False, "error_msg": f"API 요청 실패 (HTTP {response.status_code}): {response.text}"}
                
            res_data = response.json()
            res_body = res_data.get("body", res_data)
            
            return_code = res_body.get("return_code")
            if return_code is not None and int(return_code) != 0:
                return {"success": False, "error_msg": f"API 오류: {res_body.get('return_msg', '알 수 없는 오류')}"}
                
            holdings = res_body.get("day_bal_rt", [])
            if holdings:
                for h in holdings:
                    if "stk_cd" in h:
                        h["stk_cd"] = clean_stock_code(h["stk_cd"])
                all_holdings.extend(holdings)
                
            res_headers = response.headers
            cont_yn = res_headers.get("cont-yn", "N")
            next_key = res_headers.get("next-key", "")
            
            if cont_yn != "Y" or not next_key:
                break
                
        except Exception as e:
            return {"success": False, "error_msg": f"네트워크 오류 또는 예외 발생: {str(e)}"}
            
    return {
        "success": True,
        "holdings": all_holdings
    }
