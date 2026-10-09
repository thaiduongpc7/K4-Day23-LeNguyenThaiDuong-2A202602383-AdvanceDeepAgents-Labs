"""check_citations.py - STUDENT IMPLEMENTS `check`.   Runs INSIDE the sandbox (standard library only).

research.py uploads this file to the sandbox and the lead agent runs it with the `execute` tool:
    python3 /tmp/work/research/check_citations.py [report.md] [sources.json]
It must exit 0 and print "OK: ..." when the report is consistent, else print each problem and exit 1.
"""
import json
import re
import sys

REPORT = "/tmp/work/report/report.md"
SOURCES = "/tmp/work/research/sources.json"
_REF_HEADING = re.compile(r"(?m)^##[ \t]+References[ \t]*$")
_CITE = re.compile(r"\[(\d+(?:\s*(?:,|[-\u2013])\s*\d+)*)\](?!\()")
_CODE = re.compile(r"(```.*?```|`[^`\n]*`)", re.DOTALL)
_REF_LINE = re.compile(r"^\[(\d+)\]\s+(.+)$")
_URL = re.compile(r"https?://[^\s)]+")


def _citation_numbers(group):
    numbers = []
    for part in re.split(r"\s*,\s*", group):
        match = re.fullmatch(r"(\d+)\s*[-\u2013]\s*(\d+)", part)
        if match:
            start, end = int(match.group(1)), int(match.group(2))
            if 0 <= end - start <= 200:
                numbers.extend(range(start, end + 1))
            else:
                numbers.extend([start, end])
        else:
            numbers.append(int(part))
    return numbers


def _body_citations(body):
    cited = set()
    for index, segment in enumerate(_CODE.split(body)):
        if index % 2:
            continue
        for match in _CITE.finditer(segment):
            cited.update(_citation_numbers(match.group(1)))
    return cited


def check(report_text, sources):
    """Return a list of problem strings (empty list = OK).

    PSEUDO-CODE:
      problems = []
      if sources is empty: return ["no sources in sources.json"]
      for each source entry:
          n must be an int                       -> problem if not
          url must start with http:// or https://-> problem if not
          the same url must not appear twice     -> problem if duplicated
      split report_text at the heading "## References":
          body = text before it; if the heading is missing -> problem
      cited = set of numbers found as [n] in the BODY only (not in the reference list; use a regex)
      every number in `cited` must exist in sources -> problem "[n] cited but missing from sources.json"
      every source number must be in `cited`        -> problem "source [n] never cited"
      the lines of the References section that start with "[n]" (regex) are the reference lines:
          every source needs exactly ONE reference line (none missing, no number twice, no number that is not a source)
          each reference line holds exactly ONE http(s) URL and it must equal that source's url
          (a line bundling several sources under one number is a problem)
      return problems
    """
    problems = []
    if not isinstance(sources, list) or not sources:
        return ["no sources in sources.json"]

    by_n = {}
    url_owner = {}
    for index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            problems.append(f"source #{index} is not an object")
            continue
        n = source.get("n")
        url = source.get("url")
        if not isinstance(n, int):
            problems.append(f"source #{index} has non-integer n: {n!r}")
        elif n in by_n:
            problems.append(f"duplicate source number [{n}] in sources.json")
        else:
            by_n[n] = source
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            problems.append(f"source [{n}] has invalid url: {url!r}")
        elif url in url_owner:
            problems.append(f"duplicate url in sources.json: {url}")
        else:
            url_owner[url] = n

    matches = list(_REF_HEADING.finditer(report_text or ""))
    if not matches:
        problems.append("missing ## References heading")
        body = report_text or ""
        references = ""
    else:
        body = report_text[: matches[-1].start()]
        references = report_text[matches[-1].end():]

    cited = _body_citations(body)
    for n in sorted(cited - set(by_n)):
        problems.append(f"[{n}] cited but missing from sources.json")
    for n in sorted(set(by_n) - cited):
        problems.append(f"source [{n}] never cited")

    ref_counts = {}
    ref_urls = {}
    for line in references.splitlines():
        match = _REF_LINE.match(line.strip())
        if not match:
            continue
        n = int(match.group(1))
        ref_counts[n] = ref_counts.get(n, 0) + 1
        urls = _URL.findall(match.group(2))
        if len(urls) != 1:
            problems.append(f"reference [{n}] must contain exactly one URL, found {len(urls)}")
        else:
            ref_urls.setdefault(n, urls[0])

    for n in sorted(by_n):
        if ref_counts.get(n, 0) == 0:
            problems.append(f"missing reference line for source [{n}]")
        elif ref_counts[n] > 1:
            problems.append(f"duplicate reference lines for source [{n}]")
        elif ref_urls.get(n) != by_n[n].get("url"):
            problems.append(f"reference [{n}] URL does not match sources.json")

    for n in sorted(set(ref_counts) - set(by_n)):
        problems.append(f"reference [{n}] is not in sources.json")

    return problems


def main(argv):
    report_path = argv[1] if len(argv) > 1 else REPORT
    sources_path = argv[2] if len(argv) > 2 else SOURCES
    try:
        with open(report_path, encoding="utf-8") as f:
            report = f.read()
        with open(sources_path, encoding="utf-8") as f:
            sources = json.load(f)
    except (OSError, ValueError) as exc:
        print(f"cannot read inputs: {exc}")
        return 1
    problems = check(report, sources)
    if problems:
        print("\n".join(problems))
        return 1
    print(f"OK: {len(sources)} sources, all citations resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
