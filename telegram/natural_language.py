import os
import json
import logging
import requests

logger = logging.getLogger(__name__)

from config.config import perplexity_api_key, perplexity_model

def parse_natural_language_to_commands(text: str) -> list:
    """
    사용자의 자연어 메시지를 ai-stock 명령어 리스트로 변환합니다.
    Perplexity API를 사용하여 처리합니다.
    """
    if not perplexity_api_key:
        logger.warning("Perplexity API Key가 설정되지 않았습니다.")
        return []

    # 1. 가이드 파일 로드
    guide_path = "command_guide.md"
    if not os.path.exists(guide_path):
        # 절대 경로로 찾기
        guide_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "command_guide.md"))
        
    if not os.path.exists(guide_path):
        logger.error(f"command_guide.md 파일을 찾을 수 없습니다: {guide_path}")
        return []
        
    with open(guide_path, "r", encoding="utf-8") as f:
        guide_content = f.read()

    # 2. Perplexity API 사용하여 변환
    logger.info("[NaturalLanguage] Perplexity API를 사용하여 변환을 시도합니다.")
    return _query_perplexity(text, guide_content)

def _query_perplexity(text: str, guide_content: str) -> list:
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {perplexity_api_key}",
        "Content-Type": "application/json"
    }
    
    prompt = (
        "You are a translation assistant for a Kiwoom stock trading bot.\n"
        "Your job is to convert natural language queries into Kiwoom stock bot commands.\n\n"
        "Here is the command guide for reference:\n"
        "---\n"
        f"{guide_content}\n"
        "---\n\n"
        "Requirements:\n"
        "1. Analyze the user request.\n"
        "2. Convert it to a JSON array of commands. Example: [\"buy 005930 10\"] or [\"buy 005930 10\", \"ccl #45\"]\n"
        "3. If the user request does not match any commands or cannot be converted, return an empty JSON array: []\n"
        "4. Do not include markdown formatting or block quotes in your response. Just return raw JSON.\n\n"
        f"User Request: \"{text}\""
    )
    
    payload = {
        "model": perplexity_model or "sonar",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code != 200:
            logger.error(f"[Perplexity] API 호출 실패 (HTTP {response.status_code}): {response.text}")
            return []
            
        data = response.json()
        result_text = data["choices"][0]["message"]["content"].strip()
        logger.info(f"[Perplexity] AI 응답 결과: {result_text}")
        return _parse_json_result(result_text)
    except Exception as e:
        logger.error(f"[Perplexity] 자연어 처리 중 오류 발생: {e}")
        return []

def _parse_json_result(result_text: str) -> list:
    cleaned_text = result_text.strip()
    
    # 1. 마크다운 코드 블록 제거
    if cleaned_text.startswith("```"):
        first_line_end = cleaned_text.find("\n")
        if first_line_end != -1:
            cleaned_text = cleaned_text[first_line_end:].strip()
        else:
            cleaned_text = cleaned_text[3:].strip()
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3].strip()
            
    # 2. 대괄호/중괄호 바깥의 불필요한 문자 제거
    start_idx = -1
    for idx, char in enumerate(cleaned_text):
        if char in ('[', '{'):
            start_idx = idx
            break
    
    end_idx = -1
    for idx in range(len(cleaned_text) - 1, -1, -1):
        if cleaned_text[idx] in (']', '}'):
            end_idx = idx
            break
            
    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
        cleaned_text = cleaned_text[start_idx:end_idx+1]
        
    parsed = json.loads(cleaned_text)
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if item]
    return []
