"""The investigation: refine, search, filter, scrape, summarize, pivots, save."""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Optional

import store
from config import (
    DEFAULT_CONTENT_CHARS,
    DEFAULT_MAX_RESULTS,
    DEFAULT_MAX_SCRAPE,
    DEFAULT_PRESET,
    DEFAULT_THREADS,
    RobinConfig,
    redact_secrets,
)
from llm import (
    filter_results,
    generate_summary,
    get_llm,
    refine_query,
    suggest_pivots,
)
from llm_utils import BufferedStreamingHandler
from prompts import PRESETS
from scrape import scrape_multiple
from search import engines_unreachable, get_search_results_detailed

logger = logging.getLogger(__name__)

STATUS_OK = "ok"
STATUS_NO_RESULTS = "no_results"
# Told apart from no_results: nothing was found out, rather than nothing exists.
STATUS_ENGINES_UNREACHABLE = "engines_unreachable"
STATUS_NOTHING_RELEVANT = "nothing_relevant"
# The filter kept results and the scraper could not read a single one of them:
# every onion service down, slow or refusing. Stopping here is the same honesty
# as nothing_relevant.
STATUS_NOTHING_READABLE = "nothing_readable"

# Stage name -> the phrase a caller puts after "Failed to ..." in the UI's
# error box and the MCP server's failure reply.
STAGE_ACTIONS = {
    "load_llm": "load the selected LLM",
    "refine": "refine the query",
    "search": "search the dark web",
    "filter": "filter the search results",
    "scrape": "scrape the selected pages",
    "summarize": "generate the investigation summary",
}


# Model names that record who wrote a report rather than a model Robin can
# build: robin_save_investigation stores "host", and a run through MCP
# sampling stores "host sampling".
HOST_MODEL_MARKERS = frozenset({"host", "host sampling"})


def followup_model(stored: Optional[str], selected: str,
                   resolvable: Callable[[str], bool]) -> str:
    """The model a follow-up question about a saved report runs on.

    The report's own model when `resolvable` accepts it, so a follow-up sounds
    like the report; otherwise `selected`. A resolver that raises means "no".
    """
    name = (stored or "").strip()
    if not name or name.lower() in HOST_MODEL_MARKERS:
        return selected
    try:
        return name if resolvable(name) else selected
    except Exception:
        return selected


class PipelineError(RuntimeError):
    """A stage failed. Carries which one, and the error underneath."""

    def __init__(self, stage: str, original: Exception):
        self.stage = stage
        self.action = STAGE_ACTIONS.get(stage, stage)
        self.original = original
        super().__init__("Failed to {}: {}".format(self.action, original))


@dataclass
class Investigation:
    """Everything one investigation produced, and what it ran with."""

    query: str
    status: str = STATUS_OK
    refined: str = ""
    results: List[dict] = field(default_factory=list)
    # What the engines did, when the search reported it: an empty result
    # list means nothing found only if an engine actually answered.
    search_stats: dict = field(default_factory=dict)
    filtered: List[dict] = field(default_factory=list)
    scraped: dict = field(default_factory=dict)
    summary: str = ""
    pivots: List[str] = field(default_factory=list)
    model: str = ""
    preset: str = DEFAULT_PRESET
    preset_label: str = ""
    custom_instructions: str = ""
    # The depth this run actually used, not the defaults it might have used.
    max_results: int = DEFAULT_MAX_RESULTS
    max_scrape: int = DEFAULT_MAX_SCRAPE
    content_chars: int = DEFAULT_CONTENT_CHARS
    threads: int = DEFAULT_THREADS
    started_at: str = ""
    finished_at: str = ""
    # The file `store.save_investigation` wrote, or None when it could not.
    saved_as: Optional[str] = None

    def to_record(self) -> dict:
        """The JSON body written to disk.

        The first seven keys keep their original names so older Robin versions
        can still open these files. Raw scraped text is not persisted.
        """
        return {
            "timestamp": self.started_at,
            "query": self.query,
            "refined_query": self.refined,
            "model": self.model,
            "preset": self.preset_label or self.preset,
            "sources": self.filtered,
            "summary": self.summary,
            "status": self.status,
            "preset_key": self.preset,
            "custom_instructions": self.custom_instructions,
            "results_count": len(self.results),
            "scraped_count": len(self.scraped or {}),
            "max_results": self.max_results,
            "max_scrape": self.max_scrape,
            "content_chars": self.content_chars,
            "threads": self.threads,
            "pivots": self.pivots,
            "finished_at": self.finished_at,
        }


def _preset_label(preset: str) -> str:
    entry = PRESETS.get(preset)
    return entry[0] if entry else preset


def _now() -> str:
    return datetime.now().isoformat()


def run_investigation(cfg: Optional[RobinConfig],
                      query: str,
                      model: str,
                      preset: str = DEFAULT_PRESET,
                      custom_instructions: str = "",
                      max_results: int = DEFAULT_MAX_RESULTS,
                      max_scrape: int = DEFAULT_MAX_SCRAPE,
                      content_chars: int = DEFAULT_CONTENT_CHARS,
                      threads: int = DEFAULT_THREADS,
                      on_stage: Optional[Callable[[str, Investigation], None]] = None,
                      on_token: Optional[Callable[[str], None]] = None,
                      search_fn: Optional[Callable] = None,
                      scrape_fn: Optional[Callable] = None,
                      investigations_dir=None,
                      preset_label: Optional[str] = None,
                      llm_factory: Optional[Callable[[], object]] = None,
                      save: bool = True) -> Investigation:
    """Run one investigation start to finish and return it."""
    def build_llm():
        return llm_factory() if llm_factory is not None else get_llm(model, cfg)
    def stage(name):
        if on_stage:
            on_stage(name, inv)

    inv = Investigation(
        query=query,
        model=model,
        preset=preset,
        preset_label=preset_label or _preset_label(preset),
        custom_instructions=custom_instructions or "",
        max_results=max_results,
        max_scrape=max_scrape,
        content_chars=content_chars,
        threads=threads,
        started_at=_now(),
    )

    # Stage 1 - the model
    stage("load_llm")
    try:
        llm = build_llm()
    except Exception as exc:
        raise PipelineError("load_llm", exc) from exc

    # Stage 2 - refine the query
    stage("refine")
    try:
        inv.refined = refine_query(llm, query)
    except Exception as exc:
        raise PipelineError("refine", exc) from exc

    # Stage 3 - search. The `+` encoding lives in the search layer, so this
    # hands over the refined query verbatim.
    stage("search")
    try:
        outcome = (search_fn(inv.refined, threads) if search_fn is not None
                   else get_search_results_detailed(inv.refined, max_workers=threads))
        inv.results = list(outcome["results"])
        inv.search_stats = dict(outcome["stats"])
    except Exception as exc:
        raise PipelineError("search", exc) from exc

    if not inv.results:
        return _finish(inv, STATUS_ENGINES_UNREACHABLE
                       if engines_unreachable(inv.search_stats) else STATUS_NO_RESULTS)

    # The user's cap applies before the model is asked to rank anything.
    if len(inv.results) > max_results:
        inv.results = inv.results[:max_results]

    # Stage 4 - filter
    stage("filter")
    try:
        inv.filtered = list(filter_results(llm, inv.refined, inv.results,
                                           limit=max_scrape) or [])
    except Exception as exc:
        raise PipelineError("filter", exc) from exc

    if not inv.filtered:
        # Nothing on topic. Robin stops here on purpose rather than summarizing
        # unrelated pages.
        return _finish(inv, STATUS_NOTHING_RELEVANT)

    if len(inv.filtered) > max_scrape:
        inv.filtered = inv.filtered[:max_scrape]

    # Stage 5 - scrape
    stage("scrape")
    try:
        if scrape_fn is not None:
            inv.scraped = scrape_fn(inv.filtered, threads, content_chars) or {}
        else:
            inv.scraped = scrape_multiple(inv.filtered, max_workers=threads,
                                          max_return_chars=content_chars) or {}
    except Exception as exc:
        raise PipelineError("scrape", exc) from exc

    if not inv.scraped:
        # Not one kept page could be read over Tor. No summary, no pivots, no
        # save: there is nothing to write them from.
        return _finish(inv, STATUS_NOTHING_READABLE)

    # Stage 6 - summarize, streaming through the caller's callback
    stage("summarize")
    streamed = {"text": ""}

    def _emit(chunk: str) -> None:
        streamed["text"] += chunk
        if on_token:
            on_token(chunk)

    llm.callbacks = [BufferedStreamingHandler(ui_callback=_emit)]
    try:
        returned = generate_summary(llm, query, inv.scraped, preset=preset,
                                    custom_instructions=custom_instructions)
    except Exception as exc:
        raise PipelineError("summarize", exc) from exc

    # Reasoning models (OpenAI o1, DeepSeek R1 and similar) may stream no answer
    # tokens, leaving the streamed buffer empty; generate_summary's return value
    # still holds the answer, so it is the fallback.
    inv.summary = streamed["text"] if streamed["text"].strip() else (returned or "")
    if not inv.summary.strip():
        raise PipelineError("summarize", RuntimeError("the model returned an empty report"))

    # Pivots are a convenience and never block a finished investigation. A
    # fresh client, so the structured JSON is not streamed to the caller.
    stage("pivots")
    try:
        inv.pivots = list(suggest_pivots(build_llm(), query, inv.scraped,
                                         preset=preset) or [])
    except Exception as exc:
        logger.warning("Pivot suggestions failed (%s).", redact_secrets(exc, cfg)[:200])
        inv.pivots = []

    # The MCP server passes save=False and saves the finished run itself,
    # through the same scrubbing, bounds and per-session allowance as its save
    # tool. The UI keeps the default and saves here.
    if not save:
        return _finish(inv, STATUS_OK)

    stage("save")
    _finish(inv, STATUS_OK)
    return store.save_investigation(inv, investigations_dir=investigations_dir, cfg=cfg)


def _finish(inv: Investigation, status: str) -> Investigation:
    inv.status = status
    inv.finished_at = _now()
    return inv
