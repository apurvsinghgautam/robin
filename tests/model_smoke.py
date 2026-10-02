"""Opt-in live model checks using synthetic data; no Tor or real investigations."""
import argparse
import json
import re
import time
from importlib.metadata import version
from pathlib import Path

import llm
import pipeline
from config import RobinConfig, redact_secrets
from prompts import preset_sections


CVE = "CVE-2026-12345"
HASH = "0123456789abcdef" * 4
EMAIL = "analyst@example.com"
QUERY = f"{CVE} {HASH} {EMAIL} investigation"
SOURCE = "http://" + "a" * 56 + ".onion/advisory"
FOLLOWUP_SOURCE = "http://" + "b" * 56 + ".onion/update"
RESULTS = [
    {"link": "http://" + "c" * 56 + ".onion", "title": "Baseball scores archive"},
    {"link": SOURCE, "title": f"Synthetic advisory {CVE} {HASH} {EMAIL}"},
    {"link": "http://" + "d" * 56 + ".onion", "title": "Apple cider recipes"},
    {"link": FOLLOWUP_SOURCE, "title": f"Synthetic advisory update {CVE} {EMAIL}"},
]
PAGES = {
    SOURCE: f"Synthetic test data. Advisory identifies {CVE}. Sample SHA-256: {HASH}. "
            f"Contact: {EMAIL}. This is an unverified forum claim; no victims, "
            "ransomware group, cryptocurrency address, or exploitation date are given.",
    FOLLOWUP_SOURCE: f"Synthetic test data. Follow-up repeats {CVE} and {EMAIL}. "
                     "No independent confirmation or additional indicators are provided.",
}
PACKAGES = ("langchain-core", "langchain-openai", "langchain-anthropic",
            "langchain-google-genai", "langchain-mistralai", "langchain-ollama",
            "openai", "anthropic", "google-genai")


def report_checks(report):
    def section(heading):
        match = re.search(r"(?ms)^" + re.escape(heading) + r"[ \t]*\r?\n(.*?)(?=^## |\Z)", report)
        return match.group(1) if match else ""

    artifacts = section("## Investigation Artifacts")
    sources = section("## Source Links Referenced for Analysis")
    return {
        "report_identifiers": all(value in artifacts for value in (CVE, HASH, EMAIL)),
        "source_links": all(url in sources for url in PAGES),
        "report_sections": all(heading in report for heading in preset_sections("threat_intel")),
        "no_extra_artifacts": (
            set(re.findall(r"CVE-\d{4}-\d{4,}", report, re.I)) <= {CVE}
            and set(re.findall(r"\b[a-fA-F0-9]{64}\b", report)) <= {HASH}
            and set(re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", report)) <= {EMAIL}
        ),
        "decoys_excluded": not any(word in report.lower() for word in ("baseball", "cider")),
        "answer_only": not re.match(r"\s*<(think|thinking)>", report, re.I),
    }


def evaluate(model, cfg, llm_factory=None):
    """Exercise real stages and retain outputs for review, not just a pass label."""
    started = time.monotonic()
    record = {"model": model, "checks": {}, "outputs": {}}
    checks, outputs = record["checks"], record["outputs"]

    def build():
        client = llm_factory() if llm_factory else llm.get_llm(model, cfg)
        if hasattr(client, "request_timeout"):
            client.request_timeout = 90
        elif hasattr(client, "timeout"):
            client.timeout = 90
        if hasattr(client, "max_retries"):
            client.max_retries = 0
        return client

    try:
        inv = pipeline.run_investigation(
            cfg, QUERY, model, max_results=4, max_scrape=2, save=False,
            llm_factory=build,
            search_fn=lambda query, threads: {"results": RESULTS, "stats": {}},
            scrape_fn=lambda selected, threads, chars: {
                row["link"]: PAGES[row["link"]] for row in selected if row["link"] in PAGES},
        )
        outputs.update(refined=inv.refined, selected=inv.filtered,
                       report=inv.summary, pivots=inv.pivots, status=inv.status)
        checks["identifiers_preserved"] = all(value in inv.refined for value in (CVE, HASH, EMAIL))
        checks["relevant_selection"] = {r["link"] for r in inv.filtered} == set(PAGES)
        checks["completed_report"] = inv.status == pipeline.STATUS_OK and bool(inv.summary.strip())
        checks.update(report_checks(inv.summary))
        checks["usable_pivots"] = bool(inv.pivots) and all(isinstance(p, str) for p in inv.pivots)

        selected, raw = llm.filter_results_detailed(build(), QUERY, [RESULTS[0], RESULTS[2]], limit=2)
        outputs["irrelevant_selection"] = raw
        checks["empty_selection"] = selected == []
        context = llm.build_followup_context(QUERY, inv.refined, inv.filtered, inv.scraped, inv.summary)
        answer = llm.answer_followup(build(), "What Bitcoin address is in the source?", context, history=[])
        outputs["followup"] = answer
        checks["no_invented_wallet"] = bool(answer.strip()) and not re.search(
            r"\b(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{25,90})\b", answer)
    except Exception as exc:
        record["error"] = redact_secrets(exc, cfg)
        checks["completed_without_error"] = False
    record["elapsed_seconds"] = round(time.monotonic() - started, 2)
    record["passed"] = bool(checks) and all(checks.values())
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", required=True, help="Model names from Robin's picker")
    parser.add_argument("--runs", type=int, default=1, help="Repetitions per model (default: 1)")
    parser.add_argument("--output", type=Path, required=True, help="Write checks and generated text as JSON")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    cfg = RobinConfig.from_env()
    report = {"fixture": "synthetic-model-compatibility-v1",
              "versions": {name: version(name) for name in PACKAGES}, "runs": []}
    for model in args.models:
        for run in range(args.runs):
            record = evaluate(model, cfg)
            record["run"] = run + 1
            report["runs"].append(record)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            failed = [name for name, passed in record["checks"].items() if not passed]
            print(f"{model} run {run + 1}: {'PASS' if record['passed'] else 'FAIL'} {', '.join(failed)}", flush=True)
    return 0 if all(record["passed"] for record in report["runs"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
