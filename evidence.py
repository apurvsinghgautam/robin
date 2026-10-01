"""Source passages and artifact provenance, checked before a report is rendered."""
import hashlib
import ipaddress
import json
import re
from collections import Counter

from prompts import preset_sections
from scrape import fence_untrusted, scrub_untrusted_text


PASSAGE_CHARS = 1200
MIN_PASSAGE_CHARS = 600
MAX_ARTIFACTS = 100
MAX_FINDINGS = 20
MAX_NEXT_STEPS = 10
MAX_REPORT_CHARS = 200_000

_ARTIFACT_PATTERNS = (
    ("CVE", re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.I)),
    ("SHA-256 candidate", re.compile(r"\b[a-f0-9]{64}\b", re.I)),
    ("SHA-1 candidate", re.compile(r"(?<![\w])(?<!0x)[a-f0-9]{40}\b", re.I)),
    ("MD5 candidate", re.compile(r"\b[a-f0-9]{32}\b", re.I)),
    ("Email", re.compile(r"(?<![\w.+-])[\w.+-]{1,64}@[\w.-]{1,253}\.[a-z]{2,63}\b", re.I)),
    ("Onion domain", re.compile(r"\b(?:[a-z2-7]{16}|[a-z2-7]{56})\.onion\b", re.I)),
    ("Domain", re.compile(r"(?<![\w@.-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\b", re.I)),
    ("IPv4", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("Ethereum address candidate", re.compile(r"\b0x[a-f0-9]{40}\b", re.I)),
    ("Bitcoin address candidate", re.compile(r"\b(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{25,90})\b")),
)


def extract_artifacts(text):
    """Recognized literal identifiers; their presence does not establish a relationship."""
    found = []
    for kind, pattern in _ARTIFACT_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group()
            if kind == "Domain" and value.lower().endswith(".onion"):
                continue
            if kind == "IPv4":
                try:
                    ipaddress.IPv4Address(value)
                except ValueError:
                    continue
            item = (kind, value)
            if item not in found:
                found.append(item)
    return found


def _passages(text):
    """Contiguous excerpts, cut at whitespace when possible, never rewritten."""
    text = scrub_untrusted_text(text).strip()
    while text:
        end = min(PASSAGE_CHARS, len(text))
        if end < len(text):
            boundary = max(text.rfind(" ", MIN_PASSAGE_CHARS, end),
                           text.rfind("\n", MIN_PASSAGE_CHARS, end))
            if boundary >= MIN_PASSAGE_CHARS:
                end = boundary
        yield text[:end]
        text = text[end:].lstrip()


def build_evidence(pages):
    """Index only the text actually supplied, excluding the query and search titles."""
    passages, artifacts, sources = {}, {}, []
    for source, text in pages:
        source = scrub_untrusted_text(str(source)).replace("\n", " ").replace("\t", " ").strip()
        text = scrub_untrusted_text(str(text)).strip()
        if source not in sources:
            sources.append(source)
        tag = hashlib.sha256((source + "\0" + text).encode()).hexdigest()[:12]
        for number, quote in enumerate(_passages(text), start=1):
            key = "E{}-{}".format(tag, number)
            # Source-less list inputs can repeat the same source label.
            while key in passages:
                number += 1
                key = "E{}-{}".format(tag, number)
            passages[key] = {"source_url": source, "quote": quote}
            for kind, value in extract_artifacts(quote):
                artifact = artifacts.setdefault((kind, value), {
                    "type": kind, "value": value, "evidence_ids": []})
                artifact["evidence_ids"].append(key)
    return {"sources": sources, "passages": passages,
            "artifacts": list(artifacts.values())}


def evidence_input(index):
    """The IDs and their exact passages, inside the existing untrusted-content fences."""
    blocks = []
    for source in index["sources"]:
        rows = ["evidence_id: {}\n{}".format(key, item["quote"])
                for key, item in index["passages"].items() if item["source_url"] == source]
        blocks.append(fence_untrusted("\n\n".join(rows), source))
    return "\n\n".join(blocks)


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field in the evidence selection")
        result[key] = value
    return result


def _selection(raw):
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", text, re.S | re.I)
    if fenced:
        text = fenced.group(1)
    try:
        selected = json.loads(text, object_pairs_hook=_unique_keys)
    except (ValueError, TypeError) as exc:
        raise ValueError("the model did not return a valid evidence selection; no unchecked report was released") from exc
    if (not isinstance(selected, dict) or not isinstance(selected.get("sections"), dict)
            or not isinstance(selected.get("next_steps"), list)):
        raise ValueError("the model's evidence selection needs sections and next_steps; no unchecked report was released")
    return selected


def _literal(text):
    """Keep source text from creating Markdown headings, links or HTML of its own."""
    text = scrub_untrusted_text(str(text))
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"([\\`*_{}\[\]()#!|])", r"\\\1", text)


def _quoted(item):
    lines = ["- Source: " + _literal(item["source_url"]), ""]
    lines.extend("> " + _literal(line) for line in item["quote"].splitlines())
    return "\n".join(lines)


def render_report(query, raw, index, preset="threat_intel"):
    """Render checked source excerpts, never the model's factual paraphrases."""
    if len(query) >= MAX_REPORT_CHARS:
        raise ValueError("the source-based report exceeds the save limit; shorten the query")
    selected = _selection(raw)
    headings = [heading[3:] for heading in preset_sections(preset)]
    factual = headings[3:-1]
    accepted, rejected = {}, Counter()
    for section, items in selected["sections"].items():
        if section not in factual or not isinstance(items, list):
            rejected["invalid_section"] += 1
            continue
        keys = []
        limit = 5 if section == "Key Insights" else MAX_FINDINGS
        for key in items:
            if not isinstance(key, str) or key not in index["passages"]:
                rejected["unknown_evidence"] += 1
            elif key not in keys:
                if len(keys) < limit:
                    keys.append(key)
                else:
                    rejected["section_limit"] += 1
        accepted[section] = keys

    lines = ["## " + headings[0], _literal(query), "", "## " + headings[1]]
    lines.extend("- " + _literal(source) for source in index["sources"])
    lines.extend(["", "## " + headings[2]])
    lines.append("Observed identifiers; their presence does not establish a relationship or attribution.")
    artifacts = index["artifacts"][:MAX_ARTIFACTS]
    cited = []
    for artifact in artifacts:
        lines.append("- **{}:** {}".format(artifact["type"], _literal(artifact["value"])))
        for key in artifact["evidence_ids"]:
            lines.append("  - Source: " + _literal(index["passages"][key]["source_url"]))
            if key not in cited:
                cited.append(key)
    if not artifacts:
        lines.append("No recognized technical identifiers in the supplied excerpts.")
    if cited:
        lines.extend(["", "Supporting source passages:", ""])
        lines.extend(_quoted(index["passages"][key]) + "\n" for key in cited)
    for heading in factual:
        lines.extend(["", "## " + heading])
        keys = accepted.get(heading, [])
        if not keys:
            lines.append("Not established by the supplied excerpts.")
        for key in keys:
            lines.append(_quoted(index["passages"][key]) + "\n")

    lines.extend(["", "## " + headings[-1], "Proposed investigative actions, not findings."])
    allowed = {value for _, value in extract_artifacts(query)} | {
        item["value"] for item in index["artifacts"]}
    steps = []
    for step in selected["next_steps"]:
        if not isinstance(step, str) or not step.strip() or len(step) > 1000:
            rejected["invalid_next_step"] += 1
        elif any(value not in allowed for _, value in extract_artifacts(step)):
            rejected["invented_next_step_artifact"] += 1
        elif step not in steps:
            if len(steps) < MAX_NEXT_STEPS:
                steps.append(step)
            else:
                rejected["next_step_limit"] += 1
    lines.extend("- " + _literal(step) for step in steps)
    if not steps:
        lines.append("No supported next steps proposed.")
    lines.extend(["", "Source passages are quoted evidence of what a page says; they are not independent confirmation."])
    if rejected:
        lines.append("{} invalid evidence selection(s) or proposed action(s) omitted.".format(sum(rejected.values())))
    if len(index["artifacts"]) > MAX_ARTIFACTS:
        lines.append("Artifact listing limited to the first {} identifiers.".format(MAX_ARTIFACTS))
    metadata = {
        "status": "source_matched", "format": "source-excerpts-v1",
        "accepted_findings": sum(len(keys) for keys in accepted.values()),
        "rejected": dict(rejected),
        "artifact_sources": [{"type": item["type"], "value": item["value"],
                              "sources": list(dict.fromkeys(index["passages"][key]["source_url"]
                                                            for key in item["evidence_ids"]))}
                             for item in artifacts],
    }
    report = "\n".join(lines).strip()
    if len(report) > MAX_REPORT_CHARS:
        raise ValueError("the source-based report exceeds the save limit; reduce the page count or content budget")
    return report, metadata
