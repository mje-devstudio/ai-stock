"""
HTTP 요청 속도 제한 큐 (Rate Limiter)

키움증권 REST API는 초당 5회 미만으로 요청해야 합니다.
이 모듈은 두 가지 슬라이딩 윈도우를 동시에 적용합니다.

  1. 전역 한도: 어떤 1초 구간이든 최대 4건
  2. API-ID별 한도: PER_API_LIMITS에 명시된 TR코드는 1초당 별도 한도 적용

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
    전역 + API-ID별 슬라이딩 윈도우 기반 HTTP Rate Limiter Queue.

    - 모든 요청은 동기(블로킹) 방식으로 결과를 반환합니다.
    - 대기 중인 요청 중 완전히 동일한 중복 요청(url + api-id + body)은
      맨 앞의 것만 남기고 제거합니다.
    - 워커 스레드가 큐에서 요청을 꺼내 속도 제한을 지키며 실행합니다.
    """

    # 전역 기본 한도 (로그인 후 set_global_max()로 모드별 조정)
    # 모의투자: 초당 5건 → 안전값 4
    # 실전투자: 초당 20건 → 안전값 16
    _DEFAULT_GLOBAL_MAX = 4
    WINDOW = 1.0  # 슬라이딩 윈도우 크기 (초)

    # API-ID별 한도 (1초 슬라이딩 윈도우 내 최대 호출 수)
    # 명시되지 않은 API-ID는 전역 한도(GLOBAL_MAX)만 적용됨
    PER_API_LIMITS = {
        "ka10007": 1,   # 시세표성정보요청       — per-TR 제한 확인, 1/초로 제한
        "ka10080": 1,   # 주식분봉차트조회요청   — 데이터량 많음
        "ka10001": 2,   # 주식기본정보요청
        "kt00004": 1,   # 계좌평가현황요청
        "ka01690": 1,   # 일별잔고수익률
    }

    def __init__(self):
        self.GLOBAL_MAX = self._DEFAULT_GLOBAL_MAX  # 로그인 후 조정 가능
        self._queue: deque = deque()
        self._lock = threading.Lock()
        self._queue_not_empty = threading.Condition(self._lock)

        # 슬라이딩 윈도우용 타임스탬프 (워커 스레드 전용 → 별도 lock 불필요)
        self._global_times: deque = deque()    # 전역 전송 시각
        self._api_times: dict = {}             # { api_id: deque of timestamps }

        # 워커 스레드 시작
        self._worker = threading.Thread(
            target=self._run, daemon=True, name="HttpQueueWorker"
        )
        self._worker.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def post(
        self,
        url: str,
        headers: dict = None,
        json: dict = None,
        timeout: int = 10,
        **kwargs,
    ) -> requests.Response:
        """
        동기식 HTTP POST 요청. 큐를 경유하여 속도 제한을 준수합니다.
        기존 requests.post()와 동일한 인터페이스입니다.
        headers 안의 'api-id' 값을 자동으로 감지해 per-API 한도를 적용합니다.
        """
        event = threading.Event()
        result_holder = [None]

        h = headers or {}
        api_id = h.get("api-id", "")

        entry = {
            "url": url,
            "headers": h,
            "json": json,
            "timeout": timeout,
            "kwargs": kwargs,
            "event": event,
            "result": result_holder,
            "api_id": api_id,
            "key": self._make_key(url, api_id, json),
        }

        with self._queue_not_empty:
            self._deduplicate_and_enqueue(entry)
            self._queue_not_empty.notify()

        # 워커가 처리할 때까지 블로킹 대기
        event.wait(timeout=timeout + 5)

        response = result_holder[0]
        if isinstance(response, Exception):
            raise response
        return response

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_key(self, url: str, api_id: str, body) -> str:
        """url + api-id + body로 중복 판별 해시 키를 생성합니다.
        authorization 토큰은 제외하여 토큰 갱신 시에도 동일 요청으로 인식합니다."""
        try:
            raw = json.dumps(
                {"url": url, "api_id": api_id, "body": body},
                sort_keys=True,
                ensure_ascii=False,
            )
        except (TypeError, ValueError):
            raw = f"{url}|{api_id}|{body}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _deduplicate_and_enqueue(self, new_entry: dict):
        """
        대기 큐에서 동일 키를 가진 요청이 있으면 새 요청을 큐에 추가하지 않고
        기존 요청에 구독자로 등록합니다. 기존 요청 완료 시 같은 결과가 반환됩니다.
        """
        new_key = new_entry["key"]
        for existing in self._queue:
            if existing["key"] == new_key:
                if "subscribers" not in existing:
                    existing["subscribers"] = []
                existing["subscribers"].append(
                    {"event": new_entry["event"], "result": new_entry["result"]}
                )
                logging.debug(
                    f"[HttpQueue] 중복 요청 제거: {new_entry['url']} "
                    f"api-id={new_entry['api_id']} (key={new_key[:8]}...)"
                )
                return

        self._queue.append(new_entry)

    def _run(self):
        """워커 스레드 메인 루프."""
        while True:
            with self._queue_not_empty:
                while not self._queue:
                    self._queue_not_empty.wait()
                entry = self._queue.popleft()

            self._throttle(entry["api_id"])
            self._execute(entry)

    def _throttle(self, api_id: str):
        """
        전역 + API-ID별 슬라이딩 윈도우를 모두 준수하도록 대기합니다.

        전역 한도(GLOBAL_MAX)와 API-ID별 한도(PER_API_LIMITS) 중
        어느 하나라도 초과하면 여유가 생길 때까지 대기합니다.
        """
        api_max = self.PER_API_LIMITS.get(api_id) if api_id else None

        if api_id and api_id not in self._api_times:
            self._api_times[api_id] = deque()

        while True:
            now = time.monotonic()

            # 만료된 전역 타임스탬프 제거
            while self._global_times and now - self._global_times[0] >= self.WINDOW:
                self._global_times.popleft()

            # 만료된 API별 타임스탬프 제거
            if api_id and api_max is not None:
                api_deque = self._api_times[api_id]
                while api_deque and now - api_deque[0] >= self.WINDOW:
                    api_deque.popleft()
            else:
                api_deque = None

            global_ok = len(self._global_times) < self.GLOBAL_MAX
            api_ok = api_deque is None or len(api_deque) < api_max

            if global_ok and api_ok:
                break

            # 가장 빨리 여유가 생기는 시점까지 대기
            candidates = []
            if not global_ok and self._global_times:
                candidates.append(self._global_times[0] + self.WINDOW)
            if not api_ok and api_deque:
                candidates.append(api_deque[0] + self.WINDOW)

            wait_until = min(candidates) if candidates else now + self.WINDOW
            sleep_secs = wait_until - time.monotonic()
            if sleep_secs > 0:
                time.sleep(sleep_secs)

        # 전송 시각 기록
        ts = time.monotonic()
        self._global_times.append(ts)
        if api_id and api_max is not None:
            self._api_times[api_id].append(ts)

    def _execute(self, entry: dict):
        """실제 HTTP 요청 실행 후 결과를 모든 대기 호출자에게 전달합니다."""
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

        entry["result"][0] = result
        entry["event"].set()

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


def http_post(
    url: str,
    headers: dict = None,
    json: dict = None,
    timeout: int = 10,
    **kwargs,
) -> requests.Response:
    """
    Rate Limiter를 경유하는 HTTP POST 요청 함수.
    api/ 모듈에서 requests.post() 대신 이 함수를 사용하십시오.

    헤더의 'api-id' 값을 자동으로 감지해 PER_API_LIMITS에 따른
    per-TR 속도 제한을 전역 한도와 함께 적용합니다.
    """
    return _get_queue().post(url, headers=headers, json=json, timeout=timeout, **kwargs)


def set_global_max(n: int):
    """
    전역 초당 최대 요청 수를 변경합니다. 로그인 후 세션 모드에 맞게 호출하십시오.

    권장값:
        모의투자 (paper): 4   (서버 한도 5/초의 안전값)
        실전투자 (real):  16  (서버 한도 20/초의 안전값)

    사용 예:
        from utils.http_queue import set_global_max
        set_global_max(16)  # 실전투자 로그인 후
    """
    q = _get_queue()
    q.GLOBAL_MAX = n
    logging.info(f"[HttpQueue] 전역 초당 최대 요청 수를 {n}건으로 변경했습니다.")
