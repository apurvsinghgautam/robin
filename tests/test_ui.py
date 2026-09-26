"""ui.py's contract with the pipeline, read from its source.

ui.py runs Streamlit the moment it is imported, so these tests parse it, and
execute the few pieces with logic of their own against stand-ins for `st`.
"""
import ast
import unittest
from contextlib import ExitStack

import pipeline
import search

with open("ui.py", encoding="utf-8") as _handle:
    SOURCE = _handle.read()
TREE = ast.parse(SOURCE)

PIPELINE_STAGES = {"refine_query", "filter_results", "generate_summary", "suggest_pivots"}


def called_names(tree):
    return {node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            for node in ast.walk(tree) if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Name, ast.Attribute))}


def imported_names(tree):
    return {alias.asname or alias.name for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}


def load_from_ui(names, namespace):
    """Execute ui.py's top-level definitions called `names` in `namespace`, decorators included."""
    lines = SOURCE.splitlines()
    parts = []
    for node in TREE.body:
        targets = [getattr(t, "id", "") for t in getattr(node, "targets", [])]
        if getattr(node, "name", None) in names or set(targets) & set(names):
            first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
            parts.append("\n".join(lines[first - 1:node.end_lineno]))
    exec(compile("\n\n".join(parts), "ui.py", "exec"), namespace)
    return namespace


class ThePageRunsThePipeline(unittest.TestCase):
    """The pipeline is the page's only path to an investigation."""

    def test_no_stage_is_called_or_imported_directly(self):
        self.assertEqual(PIPELINE_STAGES & (called_names(TREE) | imported_names(TREE)), set())
        self.assertIn("run_investigation", called_names(TREE))
        self.assertIn("search_fn=cached_search_results", SOURCE)
        self.assertIn("scrape_fn=cached_scrape_multiple", SOURCE)

    def test_every_status_the_pipeline_can_return_is_handled(self):
        statuses = {value for name, value in vars(pipeline).items() if name.startswith("STATUS_")}
        self.assertEqual(statuses, {"ok", "no_results", "engines_unreachable",
                                    "nothing_relevant", "nothing_readable"})
        for status in statuses - {"ok"}:
            with self.subTest(status):
                self.assertIn('investigation.status == "%s"' % status, SOURCE)
        self.assertIn("PipelineError", imported_names(TREE))


    def test_a_tor_that_is_still_starting_is_not_shown_as_connected(self):
        with open("health.py", encoding="utf-8") as handle:
            self.assertIn('"starting"', handle.read())
        self.assertIn('tor_result["status"] == "down"', SOURCE)
        self.assertIn('tor_result["status"] != "up"', SOURCE)

    def test_a_page_with_no_models_explains_itself_in_the_main_area(self):
        """A collapsed sidebar would otherwise leave a blank page, and a .env
        that Docker mounted as a folder gets its own message."""
        start = SOURCE.index("if not model_options:")
        block = SOURCE[start:SOURCE.index("st.stop()", start)]
        self.assertNotIn("st.sidebar.", block)
        self.assertEqual(block.count("st.error("), 3)
        self.assertIn('with_name(".env").is_dir()', block)

class _FakeCache:
    """`st.cache_data` with a per-arguments `.clear`, recording every real call."""

    def __init__(self):
        self.calls = []

    def cache_data(self, **_):
        def decorate(fn):
            memo = {}

            def cached(*args):
                if args not in memo:
                    self.calls.append(args)
                    memo[args] = fn(*args)
                return memo[args]
            cached.clear = lambda *args: memo.pop(args, None)
            return cached
        return decorate


class TheSearchCache(unittest.TestCase):
    """The cached search keeps the engine statistics and never caches an outage."""

    def test_an_outage_searches_again_and_an_answer_is_reused(self):
        cases = [
            ("outage", {"engines_answered": 0, "engines_empty": 0, "engines_failed": 16}, 2),
            ("answer", {"engines_answered": 9, "engines_empty": 2, "engines_failed": 5}, 1),
        ]
        for name, stats, searches in cases:
            with self.subTest(name):
                outcome = {"results": [], "stats": stats}
                st = _FakeCache()
                ui = load_from_ui({"_cached_search", "cached_search_results"}, {
                    "st": st, "engines_unreachable": search.engines_unreachable,
                    "get_search_results_detailed": lambda query, max_workers: outcome})
                for _ in range(2):
                    self.assertEqual(ui["cached_search_results"]("acme leak", 4), outcome)
                self.assertEqual(len(st.calls), searches)


class _Recorder:
    """Stands in for a Streamlit slot, spinner and container, logging enter and exit."""

    def __init__(self, log, label=None):
        self.log, self.label = log, label

    def __enter__(self):
        self.log.append(("open", self.label))

    def __exit__(self, *exc):
        self.log.append(("close", self.label))

    def container(self):
        return _Recorder(self.log, "container")

    def spinner(self, label):
        return _Recorder(self.log, label)


class TheStageIndicator(unittest.TestCase):
    """One spinner at a time, each closed before the next opens."""

    def test_each_stage_replaces_the_last_and_closing_twice_is_harmless(self):
        log = []
        ui = load_from_ui({"_StageIndicator"}, {"ExitStack": ExitStack, "st": _Recorder(log)})
        indicator = ui["_StageIndicator"](_Recorder(log))
        indicator.show("first")
        indicator.show("second")
        indicator.show("")
        indicator.close()
        self.assertEqual(log, [("open", "container"), ("open", "first"),
                               ("close", "first"), ("close", "container"),
                               ("open", "container"), ("open", "second"),
                               ("close", "second"), ("close", "container")])


class _FakeTile:
    """A stat tile slot whose `empty()` clears what it shows."""

    def __init__(self, name, shown):
        self.name, self.shown = name, shown

    def empty(self):
        self.shown.pop(self.name, None)


class _Inv:
    """Just the counts the tiles read off an investigation."""

    def __init__(self, refined="", results=0, filtered=0):
        self.refined, self.results, self.filtered = refined, [{}] * results, [{}] * filtered


class TheStatTiles(unittest.TestCase):
    """Each counter shows "…" while its stage runs and its value once done."""

    def setUp(self):
        self.shown = {}
        ui = load_from_ui({"_STAGE_LABELS", "_StatTiles"}, {
            "_render_stat": lambda slot, title, value: self.shown.__setitem__(slot.name, value)})
        self.tiles = ui["_StatTiles"](
            [_FakeTile(name, self.shown) for name in ("refined", "results", "filtered")])

    def test_the_tiles_fill_stage_by_stage(self):
        steps = [
            ("load_llm", _Inv(), {}),
            ("refine", _Inv(), {"refined": "…"}),
            ("search", _Inv("acme"), {"refined": "acme", "results": "…"}),
            ("filter", _Inv("acme", 40), {"refined": "acme", "results": 40, "filtered": "…"}),
            ("scrape", _Inv("acme", 40, 7), {"refined": "acme", "results": 40, "filtered": 7}),
        ]
        for stage, inv, shown in steps:
            self.tiles.stage_started(stage, inv)
            self.assertEqual(self.shown, shown, stage)

    def test_a_run_that_stops_or_fails_leaves_no_placeholder(self):
        self.tiles.stage_started("search", _Inv("acme"))
        self.tiles.finish(_Inv("acme", 0))
        self.assertEqual(self.shown, {"refined": "acme", "results": 0})
        self.tiles.stage_started("filter", _Inv("acme", 40))
        self.tiles.fail()
        self.assertEqual(self.shown, {"refined": "acme", "results": 40})


if __name__ == "__main__":
    unittest.main()
