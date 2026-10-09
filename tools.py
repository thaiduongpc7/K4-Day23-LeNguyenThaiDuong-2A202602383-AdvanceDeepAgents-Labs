"""tools.py - STUDENT IMPLEMENTS.  Source tools for the research agents.   Guide: GUIDE.md, part 1.

Rules for every tool:
  * runs on the HOST (not in the sandbox): API keys must never enter the sandbox;
  * returns a STRING (JSON text of compact records) and NEVER raises:
        "NO RESULTS"  when the source answers with nothing,
        "ERROR: ..."  when the source keeps failing after the retries (the agent then tries another source);
  * the docstring is the tool description the LLM reads: keep it precise (what it does, what it returns, when to use it).
Try your tools without any agent:   python tools.py
"""
import json
import os
import random
import re
import threading
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

import httpx
from langchain_core.tools import tool

# ---- constants (given) ----
ARXIV_URL = "https://export.arxiv.org/api/query"  # https only: http answers 301
HF_DAILY_URL = "https://huggingface.co/api/daily_papers"
HF_SEARCH_URL = "https://huggingface.co/api/papers/search"
EXA_URL = "https://mcp.exa.ai/mcp"


class RetryableError(Exception):
    """Given. Raise it inside a call to ask with_retry to wait and try again (retry_after in seconds, optional)."""

    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


_ARXIV_LOCK = threading.Lock()
_LAST_ARXIV_CALL = 0.0
_RETRY_STATUSES = {429, 500, 502, 503, 504}


def _clamp_int(value, default, low, high):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(low, min(high, number))


def _clean(text, limit=None):
    text = " ".join(str(text or "").split())
    if limit and len(text) > limit:
        return text[: limit - 1].rstrip() + "..."
    return text


def _retry_after(response):
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _checked_response(response):
    if response.status_code in _RETRY_STATUSES:
        raise RetryableError(f"HTTP {response.status_code}", retry_after=_retry_after(response))
    response.raise_for_status()
    return response


def _redact_secrets(text):
    secret = os.getenv("EXA_API_KEY")
    if secret:
        text = text.replace(secret, "<REDACTED_EXA_API_KEY>")
    return text


def _error(exc):
    return "ERROR: " + _redact_secrets(f"{type(exc).__name__}: {exc}")


# ---- TODO 1: retry helper ----
def with_retry(fn, *, attempts=5, base=1.0, cap=30.0):
    """Call fn(); when it raises RetryableError, wait and call it again.

    PSEUDO-CODE:
      for attempt in 0 .. attempts-1:
          try: return fn()
          except RetryableError as e:
              if this was the last attempt: raise
              delay = e.retry_after if the server told us, else exponential backoff base * 2**attempt
              cap the delay at `cap` seconds; add random jitter to the exponential case
              sleep(delay)
    Use it to wrap EVERY network call below. Also treat these as retryable: HTTP 429/500/502/503/504,
    httpx.TransportError (timeouts, connection resets). Read the Retry-After header when present.
    """
    last = None
    attempts = max(1, int(attempts))
    for attempt in range(attempts):
        try:
            return fn()
        except httpx.TransportError as exc:
            last = RetryableError(str(exc))
        except httpx.HTTPStatusError as exc:
            if exc.response is None or exc.response.status_code not in _RETRY_STATUSES:
                raise
            last = RetryableError(str(exc), retry_after=_retry_after(exc.response))
        except RetryableError as exc:
            last = exc
        if attempt == attempts - 1:
            raise last
        if last.retry_after is not None:
            delay = min(float(last.retry_after), cap)
        else:
            delay = min(base * (2 ** attempt), cap) + random.uniform(0, base)
        time.sleep(delay)


def _get(url, *, params=None, timeout=30):
    def call():
        response = httpx.get(url, params=params, timeout=timeout)
        return _checked_response(response)

    return with_retry(call)


# ---- TODO 2: arXiv ----
@tool
def arxiv_search(query: str, max_results: int = 10) -> str:
    """Search arXiv papers by keywords, newest first. Returns a JSON list of {id, url, published, title, summary}."""
    # PSEUDO-CODE:
    #   keep only word characters of `query` -> terms; no terms -> "NO RESULTS" (do not call the network)
    #   respect arXiv etiquette: at least 3 seconds between two arXiv calls (remember the time of the last call)
    #   GET ARXIV_URL params: search_query="all:t1 AND all:t2 ...", sortBy=submittedDate, sortOrder=descending,
    #       max_results=clamp(max_results, 1, 30)           (wrap in with_retry)
    #   parse the Atom XML: each <entry> -> {id (last part of <id> after /abs/), url, published[:10], title, summary}
    #       collapse whitespace/newlines in title and summary; cut summary to ~600 chars
    #   no entries -> "NO RESULTS"; else json.dumps(records, ensure_ascii=False)
    #   any exception -> "ERROR: <type>: <message>"
    global _LAST_ARXIV_CALL
    try:
        terms = [term.lower() for term in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", query or "")]
        terms = [term for term in terms if term not in {"and", "or", "not"}]
        if not terms:
            return "NO RESULTS"
        max_results = _clamp_int(max_results, 10, 1, 30)
        params = {
            "search_query": " AND ".join(f"all:{term}" for term in terms),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": max_results,
            "start": 0,
        }

        def call():
            global _LAST_ARXIV_CALL
            with _ARXIV_LOCK:
                wait = 3.0 - (time.monotonic() - _LAST_ARXIV_CALL)
                if wait > 0:
                    time.sleep(wait)
                response = httpx.get(ARXIV_URL, params=params, timeout=12)
                _LAST_ARXIV_CALL = time.monotonic()
            return _checked_response(response)

        response = with_retry(call, attempts=3, base=2.0, cap=15.0)
        root = ET.fromstring(response.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        records = []
        for entry in root.findall("atom:entry", ns):
            raw_id = _clean(entry.findtext("atom:id", default="", namespaces=ns))
            arxiv_id = raw_id.rsplit("/", 1)[-1]
            arxiv_id = re.sub(r"v\d+$", "", arxiv_id)
            if not arxiv_id:
                continue
            records.append({
                "id": arxiv_id,
                "url": f"https://arxiv.org/abs/{arxiv_id}",
                "published": _clean(entry.findtext("atom:published", default="", namespaces=ns))[:10],
                "title": _clean(entry.findtext("atom:title", default="", namespaces=ns)),
                "summary": _clean(entry.findtext("atom:summary", default="", namespaces=ns), 600),
            })
        return json.dumps(records, ensure_ascii=False) if records else "NO RESULTS"
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


# ---- TODO 3: Hugging Face ----
@tool
def hf_daily_papers(limit: int = 30, date: str = "", keyword: str = "") -> str:
    """Hugging Face Daily Papers = what is trending in AI research. Returns a JSON list of
    {id, url, published, title, summary, upvotes, github, stars} sorted by upvotes. `date` is YYYY-MM-DD (empty = latest).
    `keyword` filters title/summary; there is no topic search on this endpoint (use hf_search_papers for a topic)."""
    # PSEUDO-CODE:
    #   GET HF_DAILY_URL params: limit (clamp 1..100) and date (only when given)      (with_retry)
    #   response = list of items {"paper": {id, title, summary, upvotes, githubRepo, githubStars, publishedAt}, ...}
    #   map every item to the record shape above (skip items without paper.id); url = https://huggingface.co/papers/<id>
    #   keyword -> keep records whose title+summary contains it (case-insensitive); sort by upvotes descending
    try:
        params = {"limit": _clamp_int(limit, 30, 1, 100)}
        if date:
            params["date"] = date
        data = _get(HF_DAILY_URL, params=params).json()
        records = []
        needle = (keyword or "").strip().lower()
        for item in data if isinstance(data, list) else []:
            paper = item.get("paper") or item
            paper_id = paper.get("id")
            if not paper_id:
                continue
            summary = paper.get("summary") or item.get("summary") or ""
            record = {
                "id": paper_id,
                "url": f"https://huggingface.co/papers/{paper_id}",
                "published": (paper.get("publishedAt") or item.get("publishedAt") or "")[:10],
                "title": _clean(paper.get("title") or item.get("title") or ""),
                "summary": _clean(summary, 600),
                "upvotes": int(paper.get("upvotes") or item.get("upvotes") or 0),
                "github": paper.get("githubRepo") or item.get("githubRepo") or "",
                "stars": int(paper.get("githubStars") or item.get("githubStars") or 0),
            }
            if needle and needle not in (record["title"] + " " + record["summary"]).lower():
                continue
            records.append(record)
        records.sort(key=lambda r: r["upvotes"], reverse=True)
        return json.dumps(records, ensure_ascii=False) if records else "NO RESULTS"
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@tool
def hf_search_papers(query: str, limit: int = 10) -> str:
    """Search Hugging Face papers by topic. Returns a JSON list of
    {id, url, published, title, summary, upvotes, github, stars}."""
    # PSEUDO-CODE:
    #   GET HF_SEARCH_URL params: q=query, limit (clamp 1..50)                         (with_retry)
    #   same item shape as the daily endpoint; prefer paper["ai_summary"] over paper["summary"] when present
    try:
        if not (query or "").strip():
            return "NO RESULTS"
        params = {"q": query, "limit": _clamp_int(limit, 10, 1, 50)}
        data = _get(HF_SEARCH_URL, params=params).json()
        records = []
        for item in data if isinstance(data, list) else []:
            paper = item.get("paper") or item
            paper_id = paper.get("id")
            if not paper_id:
                continue
            summary = paper.get("ai_summary") or item.get("ai_summary") or paper.get("summary") or item.get("summary") or ""
            records.append({
                "id": paper_id,
                "url": f"https://huggingface.co/papers/{paper_id}",
                "published": (paper.get("publishedAt") or item.get("publishedAt") or "")[:10],
                "title": _clean(paper.get("title") or item.get("title") or ""),
                "summary": _clean(summary, 600),
                "upvotes": int(paper.get("upvotes") or item.get("upvotes") or 0),
                "github": paper.get("githubRepo") or item.get("githubRepo") or "",
                "stars": int(paper.get("githubStars") or item.get("githubStars") or 0),
            })
        return json.dumps(records, ensure_ascii=False) if records else "NO RESULTS"
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


def _exa_endpoint():
    key = os.getenv("EXA_API_KEY")
    return f"{EXA_URL}?{urlencode({'exaApiKey': key})}" if key else EXA_URL


def _parse_sse(text):
    payloads = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            data = line[5:].strip()
            if data and data != "[DONE]":
                payloads.append(json.loads(data))
    if payloads:
        return payloads[-1]
    return json.loads(text)


def _exa_rate_limited(payload, text):
    lowered = text.lower()
    if "rate limit" in lowered or "rate-limit" in lowered or "too many requests" in lowered:
        return True
    meta = (payload.get("result") or {}).get("_meta") if isinstance(payload, dict) else None
    if isinstance(meta, dict):
        blob = json.dumps(meta, ensure_ascii=False).lower()
        return ("rate" in blob and ("limit" in blob or "limited" in blob)) or meta.get("limited") is True
    return False


def _exa_call(name, arguments, *, attempts=7):
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}}

    def call():
        response = httpx.post(
            _exa_endpoint(),
            json=request,
            headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
            timeout=60,
        )
        response = _checked_response(response)
        payload = _parse_sse(response.text)
        if _exa_rate_limited(payload, response.text):
            raise RetryableError("Exa rate limited the request", retry_after=20)
        if "error" in payload:
            raise RuntimeError(payload["error"])
        return payload

    payload = with_retry(call, attempts=attempts, base=2.0, cap=60.0)
    result = payload.get("result") or {}
    parts = result.get("content") or []
    texts = [_clean(part.get("text")) for part in parts if isinstance(part, dict) and part.get("type") == "text"]
    return "\n\n".join(text for text in texts if text)


# ---- TODO 4: web search / fetch through the Exa MCP endpoint ----
@tool
def web_search(query: str, objective: str = "", num_results: int = 5) -> str:
    """Search the web (Exa). Describe the ideal page in natural language. Returns clean text of the top results with URLs."""
    # PSEUDO-CODE:
    #   call the MCP tool "web_search_exa" with arguments {query, objective, numResults}
    #       (objective is REQUIRED by Exa: when empty, build one from the query)
    #   see GUIDE.md part 1.4 for how to call an MCP server over plain HTTP (JSON-RPC "tools/call") and read the answer
    #   read optional env EXA_API_KEY; when present it is sent to the Exa endpoint.
    #       (see GUIDE.md 1.4 for where it goes) => the key then appears in exception text: redact it before returning "ERROR: ..."
    #   WATCH OUT: read GUIDE.md 1.4 about how Exa signals "rate limited" on the free tier, and retry on it
    try:
        if not (query or "").strip():
            return "NO RESULTS"
        text = _exa_call(
            "web_search_exa",
            {
                "query": query,
                "objective": objective or f"Find reliable sources about: {query}",
                "numResults": _clamp_int(num_results, 5, 1, 10),
            },
            attempts=2,
        )
        return text if text else "NO RESULTS"
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@tool
def web_fetch(url: str) -> str:
    """Read the full content of one web page (e.g. an arXiv abstract page) as markdown. Long pages are truncated."""
    # PSEUDO-CODE: MCP tool "web_fetch_exa" with arguments {"urls": [url]}; truncate the text to ~12000 chars
    try:
        if not (url or "").strip():
            return "NO RESULTS"
        text = _exa_call("web_fetch_exa", {"urls": [url]}, attempts=7)
        return text[:12000] if text else "NO RESULTS"
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


# ---- TODO 5: registry (the researcher subagent gets exactly these) ----
SOURCE_TOOLS = [arxiv_search, hf_daily_papers, hf_search_papers, web_search, web_fetch]


if __name__ == "__main__":
    for name, fn, args in [
        ("arxiv_search", arxiv_search, {"query": "world model", "max_results": 3}),
        ("hf_daily_papers", hf_daily_papers, {"limit": 20}),
        ("hf_search_papers", hf_search_papers, {"query": "world model", "limit": 3}),
        ("web_search", web_search, {"query": "survey paper on world models", "num_results": 2}),
        ("web_fetch", web_fetch, {"url": "https://arxiv.org/abs/1803.10122"}),
    ]:
        try:
            print(f"== {name}\n{fn.invoke(args)[:400]}\n")
        except NotImplementedError as exc:
            print(f"== {name}: not implemented yet ({exc})\n")
