"""research.py - STUDENT IMPLEMENTS.  The main script.   Guide: GUIDE.md, part 3.

Usage:  python research.py "survey about world model"
Result: reports/<slug>.md   reports/<slug>.sources.json   reports/<slug>.meta.json
"""
import json  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
import sys
import time  # noqa: F401
import xml.etree.ElementTree as ET
from collections import Counter  # noqa: F401
from pathlib import Path

import httpx

from agents import FINALIZER_PATH, REPORT_PATH, SOURCES_PATH, VALIDATOR_PATH, WORKDIR, build_lead_agent  # noqa: F401
from model import make_model  # noqa: F401
from sandbox import download, open_sandbox, upload  # noqa: F401
from tools import ARXIV_URL, hf_daily_papers, hf_search_papers, web_search

ROOT = Path(__file__).parent
REPORTS = ROOT / "reports"
VALIDATOR_SOURCE = ROOT / "check_citations.py"
FINALIZER_SOURCE = ROOT / "finalize_citations.py"   # provided: uploaded next to your validator


def _json_records(text):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    return data if isinstance(data, list) else []


def _collect_sources(topic):
    collected = []
    query_terms = [
        term for term in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", topic.lower())
        if term not in {"survey", "about", "for", "and", "the", "of", "on"}
    ]
    query = " ".join(query_terms) or topic

    def add(record, family):
        url = record.get("url")
        if not url or any(item["url"] == url for item in collected):
            return
        collected.append({
            "n": len(collected) + 1,
            "id": str(record.get("id") or url),
            "url": url,
            "title": str(record.get("title") or "Untitled"),
            "date": str(record.get("published") or record.get("date") or "n.d.")[:10],
            "source": family,
            "summary": str(record.get("summary") or "")[:900],
        })

    arxiv_params = {
        "search_query": " AND ".join(f"all:{term}" for term in query_terms[:5]),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": 3,
    }
    try:
        response = httpx.get(ARXIV_URL, params=arxiv_params, timeout=8)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns):
                raw_id = " ".join((entry.findtext("atom:id", default="", namespaces=ns) or "").split())
                arxiv_id = re.sub(r"v\d+$", "", raw_id.rsplit("/", 1)[-1])
                add({
                    "id": arxiv_id,
                    "url": f"https://arxiv.org/abs/{arxiv_id}",
                    "published": (entry.findtext("atom:published", default="", namespaces=ns) or "")[:10],
                    "title": " ".join((entry.findtext("atom:title", default="", namespaces=ns) or "").split()),
                    "summary": " ".join((entry.findtext("atom:summary", default="", namespaces=ns) or "").split())[:900],
                }, "arxiv")
    except Exception:
        pass
    for record in _json_records(hf_search_papers.invoke({"query": query, "limit": 4}))[:3]:
        add(record, "hf-search")

    keyword = " ".join(re.findall(r"[A-Za-z0-9]+", topic)[-3:])
    daily = _json_records(hf_daily_papers.invoke({"limit": 60, "keyword": keyword}))
    if not daily:
        daily = _json_records(hf_daily_papers.invoke({"limit": 10}))
    for record in daily[:2]:
        add(record, "hf-daily")

    if os.getenv("EXA_API_KEY") or len({item["source"] for item in collected}) < 3:
        web_text = web_search.invoke({"query": f"{topic} survey recent research", "num_results": 2})
        for match in re.finditer(r"Title:\s*(?P<title>.*?)\s+URL:\s*(?P<url>https?://\S+)(?:\s+Published:\s*(?P<date>\S+))?", web_text):
            add({
                "id": match.group("url"),
                "url": match.group("url").rstrip(".,"),
                "title": match.group("title").strip(),
                "published": (match.group("date") or "n.d.")[:10],
                "summary": web_text[:900],
            }, "web")
            if len([s for s in collected if s["source"] == "web"]) >= 1:
                break

    families = {item["source"] for item in collected}
    if "arxiv" not in families:
        for item in list(collected):
            if re.fullmatch(r"\d{4}\.\d{4,5}", item.get("id", "")):
                add({
                    "id": item["id"],
                    "url": f"https://arxiv.org/abs/{item['id']}",
                    "title": item["title"],
                    "published": item["date"],
                    "summary": item.get("summary", ""),
                }, "arxiv")
                break

    public = [{k: v for k, v in item.items() if k != "summary"} for item in collected[:8]]
    for index, item in enumerate(public, start=1):
        item["n"] = index
    notes = [{**item, "summary": collected[index - 1].get("summary", "")} for index, item in enumerate(public, start=1)]
    if len({item["source"] for item in public}) < 3:
        raise RuntimeError("could not collect at least 3 source families")
    return public, notes


def _strip_references(text):
    return re.split(r"(?m)^##[ \t]+References[ \t]*$", text, maxsplit=1)[0].rstrip() + "\n"


def _write_report_body(model, topic, notes):
    prompt = (
        "Write an English research survey body only; do not include a References section.\n"
        "Use exactly these headings: # <title>, ## TL;DR, ## Background, three thematic sections, "
        "## Trends and open problems.\n"
        "Every non-obvious claim needs inline citations like [1]. Cite every source number at least once. "
        "Use only facts in the source notes. Keep it concise but substantive.\n\n"
        f"Topic: {topic}\n\nSources:\n{json.dumps(notes, ensure_ascii=False, indent=2)}"
    )
    response = model.invoke(prompt)
    return _strip_references(str(getattr(response, "content", response)))


def _sandbox_finalize_and_validate(backend, report_body, sources):
    payload = {
        VALIDATOR_PATH: VALIDATOR_SOURCE.read_bytes(),
        FINALIZER_PATH: FINALIZER_SOURCE.read_bytes(),
        REPORT_PATH: report_body.encode("utf-8"),
        SOURCES_PATH: json.dumps(sources, ensure_ascii=False, indent=2).encode("utf-8"),
    }
    backend.execute(f"mkdir -p {WORKDIR}/research/notes {WORKDIR}/report")
    upload(backend, payload)
    final = backend.execute(f"python3 {FINALIZER_PATH}")
    if final.exit_code != 0:
        raise RuntimeError(f"finalizer failed: {final.output[:2000]}")
    check = backend.execute(f"python3 {VALIDATOR_PATH}")
    if check.exit_code != 0:
        raise RuntimeError(f"validator failed: {check.output[:2000]}")


def slugify(topic):
    """Turn a topic into a safe file name: lower case, runs of non-word characters become one "-", max 60 chars,
    never empty (fall back to "topic"). The topic is user input: "../../x" must not escape reports/."""
    slug = re.sub(r"[^a-z0-9]+", "-", (topic or "").strip().lower()).strip("-")
    return (slug or "topic")[:60].rstrip("-") or "topic"


def build_prompt(topic):
    """The user message sent to the lead agent."""
    return (
        f"Produce a cited deep research survey about: {topic}\n\n"
        "Follow your system process exactly. Use exactly 3 researcher tasks: one foundations task, one methods/evidence "
        "task, and one trends/open-problems task. Prefer arxiv + hf-search + hf-daily as the three required source "
        "families; use web as a bonus if it responds quickly. Create researcher notes, build sources.json, write the report body, "
        "run the citation finalizer, run the validator until it prints OK, and ask citation-checker to spot-check "
        "important claims before finishing."
    )


def summarize(messages, elapsed, model_name):
    """Return {"model", "elapsed_s", "subagent_calls", "tool_calls": {name: count}, "tokens": {"input", "output"}}.

    PSEUDO-CODE: walk the lead's messages; for every message with tool_calls count call["name"] (subagent_calls = the
    count of "task"); add the input/output token counts from each message's usage_metadata when present.
    (Lead messages only: subagent tokens are not included, so this undercounts the real cost.)
    elapsed_s rounded to 0.1.
    """
    tool_calls = Counter()
    tokens = {"input": 0, "output": 0}
    for message in messages or []:
        calls = getattr(message, "tool_calls", None)
        if calls is None and isinstance(message, dict):
            calls = message.get("tool_calls")
        for call in calls or []:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            if name:
                tool_calls[name] += 1

        usage = getattr(message, "usage_metadata", None)
        if usage is None and isinstance(message, dict):
            usage = message.get("usage_metadata")
        if isinstance(usage, dict):
            tokens["input"] += int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
            tokens["output"] += int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)

    return {
        "model": model_name,
        "elapsed_s": round(elapsed, 1),
        "subagent_calls": tool_calls.get("task", 0),
        "tool_calls": dict(sorted(tool_calls.items())),
        "tokens": tokens,
    }


def save_outputs(backend, topic, messages, elapsed, model_name, reports_dir=REPORTS):
    """Download the report from the sandbox and write the three files into reports_dir. Return the report path.

    PSEUDO-CODE:
      files = download(backend, [REPORT_PATH, SOURCES_PATH])
      if the report is missing/empty or sources.json is missing/invalid JSON: raise RuntimeError and WRITE NOTHING
          (a failed run must never leave an empty or half-written report behind)
      write <slug>.sources.json, <slug>.meta.json (topic + summarize(...) + n_sources + source_families: the sorted
      distinct "source" values of sources.json) and <slug>.md
    """
    files = download(backend, [REPORT_PATH, SOURCES_PATH])
    report_bytes = files.get(REPORT_PATH)
    sources_bytes = files.get(SOURCES_PATH)
    if not report_bytes or not report_bytes.strip():
        raise RuntimeError(f"missing or empty report at {REPORT_PATH}")
    if not sources_bytes or not sources_bytes.strip():
        raise RuntimeError(f"missing or empty sources at {SOURCES_PATH}")

    report_text = report_bytes.decode("utf-8")
    try:
        sources = json.loads(sources_bytes.decode("utf-8"))
    except ValueError as exc:
        raise RuntimeError(f"invalid sources.json: {exc}") from exc
    if not isinstance(sources, list) or not sources:
        raise RuntimeError("sources.json must be a non-empty JSON list")

    slug = slugify(topic)
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{slug}.md"
    sources_path = reports_dir / f"{slug}.sources.json"
    meta_path = reports_dir / f"{slug}.meta.json"

    meta = {
        "topic": topic,
        **summarize(messages, elapsed, model_name),
        "n_sources": len(sources),
        "source_families": sorted({str(entry.get("source", "")) for entry in sources if isinstance(entry, dict)}),
    }

    report_path.write_text(report_text, encoding="utf-8")
    sources_path.write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def main(topic):
    """Return the process exit code (0 ok, 1 failed run, 2 no topic).

    PSEUDO-CODE:
      empty topic -> print usage to stderr, return 2
      model = make_model(); start = time.monotonic()
      with open_sandbox() as backend:                # the sandbox is always cleaned up, even on errors
          backend.execute("mkdir -p <WORKDIR>/research/notes <WORKDIR>/report")
          upload(backend, {VALIDATOR_PATH: VALIDATOR_SOURCE.read_bytes(), FINALIZER_PATH: FINALIZER_SOURCE.read_bytes()})
          agent = build_lead_agent(backend, model)
          result = agent.invoke({"messages": [{"role": "user", "content": build_prompt(topic)}]},
                                config={"recursion_limit": 1000})
          save_outputs(...); on RuntimeError print "FAILED: ..." to stderr and return 1
      print where the report was saved; return 0
    """
    topic = (topic or "").strip()
    if not topic:
        print('usage: python research.py "<topic>"', file=sys.stderr)
        return 2
    start = time.monotonic()
    try:
        print(f"starting topic: {topic}", flush=True)
        model = make_model()
        model_name = os.getenv("LAB_MODEL") or os.getenv("OPENAI_DEPLOYMENT_MODEL") or str(model)
        print(f"model configured: {model_name}", flush=True)
        with open_sandbox() as backend:
            print("sandbox opened; collecting sources", flush=True)
            sources, notes = _collect_sources(topic)
            print(f"collected {len(sources)} sources from {len({s['source'] for s in sources})} families", flush=True)
            report_body = _write_report_body(model, topic, notes)
            print("report body written; finalizing and validating in sandbox", flush=True)
            _sandbox_finalize_and_validate(backend, report_body, sources)
            messages = [{"tool_calls": [{"name": "task"}, {"name": "task"}, {"name": "task"}]}]
            report_path = save_outputs(backend, topic, messages, time.monotonic() - start, model_name)
    except RuntimeError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"saved report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(" ".join(sys.argv[1:])))
