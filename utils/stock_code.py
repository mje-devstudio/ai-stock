def clean_stock_code(stk_cd: str) -> str:
    """종목코드가 7자리 이상이고 맨 첫 글자가 A일 경우 이 A를 떼어내고 반환합니다."""
    if not stk_cd or not isinstance(stk_cd, str):
        return stk_cd
        
    stk_cd_str = stk_cd.strip()
    if len(stk_cd_str) >= 7 and stk_cd_str[0].upper() == 'A':
        return stk_cd_str[1:]
    return stk_cd_str
