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


def get_daily_realized_profit() -> dict:
    """
    사용자 계좌의 당일 일자별 실현손익을 조회합니다 (ka10074).
    """
    if not session.is_logged_in():
        return {"success": False, "error_msg": "로그인이 필요합니다. 먼저 login [paper|real] 명령어를 실행하세요."}
    
    import datetime
    today_str = datetime.datetime.now().strftime("%Y%m%d")
    
    url = f"{session.host_url}/api/dostk/acnt"
    
    headers = {
        "api-id": "ka10074",
        "authorization": f"Bearer {session.token}",
        "Content-Type": "application/json;charset=UTF-8"
    }
    
    body = {
        "strt_dt": today_str,
        "end_dt": today_str
    }
    
    try:
        response = requests.post(url, headers=headers, json=body, timeout=10)
        
        if response.status_code != 200:
            return {"success": False, "error_msg": f"API 요청 실패 (HTTP {response.status_code}): {response.text}"}
            
        res_data = response.json()
        res_body = res_data.get("body", res_data)
        
        return_code = res_body.get("return_code")
        if return_code is not None and int(return_code) != 0:
            return {"success": False, "error_msg": f"API 오류: {res_body.get('return_msg', '알 수 없는 오류')}"}
            
        return {
            "success": True,
            "rlzt_pl": res_body.get("rlzt_pl", "0"),
            "trde_cmsn": res_body.get("trde_cmsn", "0"),
            "trde_tax": res_body.get("trde_tax", "0"),
            "tot_buy_amt": res_body.get("tot_buy_amt", "0"),
            "tot_sell_amt": res_body.get("tot_sell_amt", "0")
        }
    except Exception as e:
        return {"success": False, "error_msg": f"네트워크 오류 또는 예외 발생: {str(e)}"}


def get_trade_value_rank() -> dict:
    """
    거래대금 상위 종목 리스트를 조회합니다 (ka10032).
    """
    if not session.is_logged_in():
        return {"success": False, "error_msg": "로그인이 필요합니다. 먼저 login [paper|real] 명령어를 실행하세요."}
    
    url = f"{session.host_url}/api/dostk/rkinfo"
    
    headers = {
        "api-id": "ka10032",
        "authorization": f"Bearer {session.token}",
        "Content-Type": "application/json;charset=UTF-8"
    }
    
    body = {
        "mrkt_tp": "000",
        "mang_stk_incls": "1",
        "stex_tp": "3"
    }
    
    try:
        response = requests.post(url, headers=headers, json=body, timeout=10)
        
        if response.status_code != 200:
            return {"success": False, "error_msg": f"API 요청 실패 (HTTP {response.status_code}): {response.text}"}
            
        res_data = response.json()
        res_body = res_data.get("body", res_data)
        
        return_code = res_body.get("return_code")
        if return_code is None:
            return_code = res_body.get("returnCode")
            
        if return_code is not None and int(return_code) != 0:
            return_msg = res_body.get("return_msg") or res_body.get("returnMsg") or "알 수 없는 오류"
            return {"success": False, "error_msg": f"API 오류: {return_msg}"}
            
        return {
            "success": True,
            "data": res_body.get("trde_prica_upper", [])
        }
    except Exception as e:
        return {"success": False, "error_msg": f"네트워크 오류 또는 예외 발생: {str(e)}"}


def get_fluctuation_rate_rank() -> dict:
    """
    전일대비 등락률 상위 종목 리스트를 조회합니다 (ka10027).
    """
    if not session.is_logged_in():
        return {"success": False, "error_msg": "로그인이 필요합니다. 먼저 login [paper|real] 명령어를 실행하세요."}
    
    url = f"{session.host_url}/api/dostk/rkinfo"
    
    headers = {
        "api-id": "ka10027",
        "authorization": f"Bearer {session.token}",
        "Content-Type": "application/json;charset=UTF-8"
    }
    
    body = {
        "mrkt_tp": "000",
        "sort_tp": "1",
        "trde_qty_cnd": "0000",
        "stk_cnd": "0",
        "crd_cnd": "0",
        "updown_incls": "1",
        "pric_cnd": "0",
        "trde_prica_cnd": "0",
        "stex_tp": "3"
    }
    
    try:
        response = requests.post(url, headers=headers, json=body, timeout=10)
        
        if response.status_code != 200:
            return {"success": False, "error_msg": f"API 요청 실패 (HTTP {response.status_code}): {response.text}"}
            
        res_data = response.json()
        res_body = res_data.get("body", res_data)
        
        return_code = res_body.get("return_code")
        if return_code is None:
            return_code = res_body.get("returnCode")
            
        if return_code is not None and int(return_code) != 0:
            return_msg = res_body.get("return_msg") or res_body.get("returnMsg") or "알 수 없는 오류"
            return {"success": False, "error_msg": f"API 오류: {return_msg}"}
            
        return {
            "success": True,
            "data": res_body.get("pred_pre_flu_rt_upper", [])
        }
    except Exception as e:
        return {"success": False, "error_msg": f"네트워크 오류 또는 예외 발생: {str(e)}"}


def get_trade_volume_rank() -> dict:
    """
    당일 거래량 상위 종목 리스트를 조회합니다 (ka10030).
    """
    if not session.is_logged_in():
        return {"success": False, "error_msg": "로그인이 필요합니다. 먼저 login [paper|real] 명령어를 실행하세요."}
    
    url = f"{session.host_url}/api/dostk/rkinfo"
    
    headers = {
        "api-id": "ka10030",
        "authorization": f"Bearer {session.token}",
        "Content-Type": "application/json;charset=UTF-8"
    }
    
    body = {
        "mrkt_tp": "000",
        "sort_tp": "1",
        "mang_stk_incls": "0",
        "crd_tp": "0",
        "trde_qty_tp": "0",
        "pric_tp": "0",
        "trde_prica_tp": "0",
        "mrkt_open_tp": "0",
        "stex_tp": "3"
    }
    
    try:
        response = requests.post(url, headers=headers, json=body, timeout=10)
        
        if response.status_code != 200:
            return {"success": False, "error_msg": f"API 요청 실패 (HTTP {response.status_code}): {response.text}"}
            
        res_data = response.json()
        res_body = res_data.get("body", res_data)
        
        return_code = res_body.get("return_code")
        if return_code is None:
            return_code = res_body.get("returnCode")
            
        if return_code is not None and int(return_code) != 0:
            return_msg = res_body.get("return_msg") or res_body.get("returnMsg") or "알 수 없는 오류"
            return {"success": False, "error_msg": f"API 오류: {return_msg}"}
            
        return {
            "success": True,
            "data": res_body.get("tdy_trde_qty_upper", [])
        }
    except Exception as e:
        return {"success": False, "error_msg": f"네트워크 오류 또는 예외 발생: {str(e)}"}


def get_popular_search_rank(qry_tp: str = "1") -> dict:
    """
    실시간 종목 조회 순위(인기 검색) 리스트를 조회합니다 (ka00198).
    qry_tp: 1(1분), 2(10분), 3(1시간), 4(당일 누적), 5(30초)
    """
    if not session.is_logged_in():
        return {"success": False, "error_msg": "로그인이 필요합니다. 먼저 login [paper|real] 명령어를 실행하세요."}
    
    url = f"{session.host_url}/api/dostk/stkinfo"
    
    headers = {
        "api-id": "ka00198",
        "authorization": f"Bearer {session.token}",
        "Content-Type": "application/json;charset=UTF-8"
    }
    
    body = {
        "qry_tp": qry_tp
    }
    
    try:
        response = requests.post(url, headers=headers, json=body, timeout=10)
        
        if response.status_code != 200:
            return {"success": False, "error_msg": f"API 요청 실패 (HTTP {response.status_code}): {response.text}"}
            
        res_data = response.json()
        res_body = res_data.get("body", res_data)
        
        return_code = res_body.get("return_code")
        if return_code is None:
            return_code = res_body.get("returnCode")
            
        if return_code is not None and int(return_code) != 0:
            return_msg = res_body.get("return_msg") or res_body.get("returnMsg") or "알 수 없는 오류"
            return {"success": False, "error_msg": f"API 오류: {return_msg}"}
            
        return {
            "success": True,
            "data": res_body.get("item_inq_rank", [])
        }
    except Exception as e:
        return {"success": False, "error_msg": f"네트워크 오류 또는 예외 발생: {str(e)}"}


