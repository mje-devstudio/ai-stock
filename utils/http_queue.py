"""
HTTP 요청 속도 제한 큐 (Rate Limiter)

키움증권 REST API는 초당 5회 미만으로 요청해야 합니다.
이 모듈은 프로그램 전체의 HTTP 요청을 초당 최대 4회로 제한하는
중앙 집중식 큐를 제공합니다.

사용법:
    from utils.http_queue import http_post
    response = http_post(url, headers=headers, json=body, timeout=10)
"""

import threading
import time
import hashlib
import json
import logging
import requests
from collections import deque


class _HttpRateLimitQueue:
    """
    초당 최대 4개의 HTTP POST 요청을 처리하는 Rate Limiter Queue.

    - 모든 요청은 동기(블로킹) 방식으로 결과를 반환합니다.
    - 대기 중인 요청 중 완전히 동일한 중복 요청은 맨 앞의 것만 남기고 제거합니다.
      (url, headers, json body 세 가지가 모두 같은 경우)
    - 워커 스레드가 큐에서 요청을 꺼내 실행하고, 각 요청의 결과를
      Event를 통해 대기 중인 호출자에게 전달합니다.
    """

    MAX_PER_SECOND = 4
    MIN_INTERVAL = 1.0 / MAX_PER_SECOND  # 0.25초

    def __init__(self):
        self._queue: deque = deque()
        self._lock = threading.Lock()
        self._queue_not_empty = threading.Condition(self._lock)
        self._last_send_time = 0.0

        # 워커 스레드 시작
        self._worker = threading.Thread(target=self._run, daemon=True, name="HttpQueueWorker")
        self._worker.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def post(self, url: str, headers: dict = None, json: dict = None,
             timeout: int = 10, **kwargs) -> requests.Response:
        """
        동기식 HTTP POST 요청. 큐를 경유하여 속도 제한을 준수합니다.
        기존 requests.post()와 동일한 인터페이스입니다.
        """
        event = threading.Event()
        result_holder = [None]  # 리스트로 감싸 스레드 간 공유

        entry = {
            "url": url,
            "headers": headers or {},
            "json": json,
            "timeout": timeout,
            "kwargs": kwargs,
            "event": event,
            "result": result_holder,
            "key": self._make_key(url, headers, json),
        }

        with self._queue_not_empty:
            self._deduplicate_and_enqueue(entry)
            self._queue_not_empty.notify()

        # 워커가 요청을 처리할 때까지 대기 (타임아웃 + 버퍼)
        event.wait(timeout=timeout + 5)

        response = result_holder[0]
        if isinstance(response, Exception):
            raise response
        return response

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_key(self, url: str, headers: dict, body) -> str:
        """url + headers + body로 요청의 중복 여부를 판별하는 해시 키를 생성합니다."""
        try:
            raw = json.dumps(
                {"url": url, "headers": headers or {}, "body": body},
                sort_keys=True, ensure_ascii=False
            )
        except (TypeError, ValueError):
            raw = f"{url}|{headers}|{body}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _deduplicate_and_enqueue(self, new_entry: dict):
        """
        대기 큐에서 new_entry와 동일한 키를 가진 기존 요청을 찾아 제거합니다.
        제거된 요청의 호출자에게는 새로 추가될 요청의 event/result를 연결하여,
        실질적으로 두 호출자 모두 맨 앞의 요청 결과를 받게 됩니다.

        큐에 이미 같은 요청이 있으면:
          - 기존 요청(맨 앞)을 유지
          - 새 요청은 큐에 넣지 않고, 기존 요청의 완료 시 같은 결과를 받도록 구독
        """
        new_key = new_entry["key"]

        for existing in self._queue:
            if existing["key"] == new_key:
                # 중복 발견 — 새 요청을 큐에 넣지 않고
                # 기존 요청에 '구독자' 목록으로 새 요청의 event/result를 추가
                if "subscribers" not in existing:
                    existing["subscribers"] = []
                existing["subscribers"].append({
                    "event": new_entry["event"],
                    "result": new_entry["result"],
                })
                logging.debug(
                    f"[HttpQueue] 중복 요청 제거: {new_entry['url']} "
                    f"(key={new_key[:8]}...)"
                )
                return  # 큐에 추가하지 않음

        # 중복 없음 — 정상 추가
        self._queue.append(new_entry)

    def _run(self):
        """워커 스레드 메인 루프. 큐에서 요청을 꺼내 속도 제한을 지키며 실행합니다."""
        while True:
            with self._queue_not_empty:
                while not self._queue:
                    self._queue_not_empty.wait()
                entry = self._queue.popleft()

            self._throttle()
            self._execute(entry)

    def _throttle(self):
        """전송 간격이 MIN_INTERVAL 이상이 되도록 대기합니다."""
        now = time.monotonic()
        elapsed = now - self._last_send_time
        if elapsed < self.MIN_INTERVAL:
            time.sleep(self.MIN_INTERVAL - elapsed)
        self._last_send_time = time.monotonic()

    def _execute(self, entry: dict):
        """실제 HTTP 요청을 실행하고 결과를 대기 중인 호출자에게 전달합니다."""
        try:
            response = requests.post(
                entry["url"],
                headers=entry["headers"],
                json=entry["json"],
                timeout=entry["timeout"],
                **entry["kwargs"],
            )
            result = response
        except Exception as e:
            result = e

        # 주 호출자에게 결과 전달
        entry["result"][0] = result
        entry["event"].set()

        # 중복으로 구독된 호출자들에게도 동일 결과 전달
        for sub in entry.get("subscribers", []):
            sub["result"][0] = result
            sub["event"].set()


# 싱글턴 인스턴스
_queue_instance: _HttpRateLimitQueue = None
_instance_lock = threading.Lock()


def _get_queue() -> _HttpRateLimitQueue:
    global _queue_instance
    if _queue_instance is None:
        with _instance_lock:
            if _queue_instance is None:
                _queue_instance = _HttpRateLimitQueue()
    return _queue_instance


def http_post(url: str, headers: dict = None, json: dict = None,
              timeout: int = 10, **kwargs) -> requests.Response:
    """
    Rate Limiter를 경유하는 HTTP POST 요청 함수.
    api/ 모듈에서 requests.post() 대신 이 함수를 사용하십시오.

    Args:
        url: 요청 URL
        headers: 요청 헤더 딕셔너리
        json: 요청 바디 (JSON으로 직렬화됨)
        timeout: 타임아웃 (초)
        **kwargs: requests.post에 전달할 추가 인자

    Returns:
        requests.Response 객체
    """
    return _get_queue().post(url, headers=headers, json=json, timeout=timeout, **kwargs)
