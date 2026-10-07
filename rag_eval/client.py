# coding=utf-8
"""MaxKB native SSE client; retries use isolated conversations."""
import json
import os
import random
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .store import now


class APIError(RuntimeError):
    pass


def request(url, payload, token, timeout):
    data = None if payload is None else json.dumps(payload).encode()
    return urlopen(Request(url, data=data, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json",
        "Accept": "text/event-stream, application/json",
    }), timeout=timeout)


def unwrap(data):
    if "code" in data and data["code"] not in (200, 0):
        raise APIError(str(data.get("message", "MaxKB API error")))
    return data.get("data", data)


def sse_events(response):
    lines = []
    for raw in response:
        line = raw.decode("utf-8").rstrip("\r\n")
        if not line:
            if lines:
                yield "\n".join(lines)
                lines = []
        elif line.startswith("data:"):
            lines.append(line[5:].lstrip(" "))
    if lines:
        yield "\n".join(lines)


def read_answer(response):
    answer, usage, record_id, ended, contexts = [], None, None, False, None
    if "text/event-stream" not in response.headers.get("Content-Type", ""):
        data = unwrap(json.load(response))
        return {"answer": data.get("content", ""), "chat_record_id": data.get("id"),
                "token_usage": data.get("usage", {
                    "prompt_tokens": data.get("prompt_tokens"), "completion_tokens": data.get("completion_tokens")}),
                "contexts": data.get("retrieval_context")}
    for event in sse_events(response):
        if event == "[DONE]":
            ended = True
            continue
        data = unwrap(json.loads(event))
        if data.get("error") or data.get("err_message"):
            raise APIError("MaxKB stream returned an error")
        answer.append(data.get("content") or "")
        record_id = data.get("chat_record_id") or record_id
        if data.get("usage") is not None:
            usage = data["usage"]
        if "retrieval_context" in data:
            contexts = data["retrieval_context"]
        ended = ended or bool(data.get("is_end"))
    if not ended:
        raise APIError("Incomplete SSE stream (missing is_end)")
    return {"answer": "".join(answer), "chat_record_id": record_id,
            "token_usage": usage, "contexts": contexts}


class MaxKBClient:
    def __init__(self, config):
        self.config = config
        self.base = config["base_url"].rstrip("/")
        self.token = os.environ[config.get("api_key_env", "MAXKB_API_KEY")]
        self.timeout = config.get("timeout", 120)
        self.retries = config.get("retries", 2)

    def ask(self, question):
        started, timestamp = time.perf_counter(), now()
        last_error = None
        for attempt in range(self.retries + 1):
            try:
                with request(self.base + "/open", None, self.token, self.timeout) as response:
                    chat_id = unwrap(json.load(response))
                if not isinstance(chat_id, str):
                    raise APIError("Unexpected /open response")
                with request(self.base + "/chat_message/" + chat_id, {
                    **self.config.get("body", {}), "message": question, "stream": True, "re_chat": False,
                }, self.token, self.timeout) as response:
                    result = read_answer(response)
                if not result["answer"].strip():
                    raise APIError("Empty answer")
                return {**result, "chat_id": chat_id, "question": question, "timestamp": timestamp,
                        "response_time": time.perf_counter() - started, "attempts": attempt + 1}
            except (HTTPError, URLError, TimeoutError, OSError, APIError, ValueError) as error:
                last_error = type(error).__name__
                if isinstance(error, HTTPError) and error.code not in (408, 429, 500, 502, 503, 504):
                    break
                if attempt < self.retries:
                    time.sleep(min(30, 2 ** attempt) + random.random())
        return {"question": question, "answer": "", "timestamp": timestamp,
                "response_time": time.perf_counter() - started, "attempts": attempt + 1,
                "error": last_error, "token_usage": None, "contexts": None}
