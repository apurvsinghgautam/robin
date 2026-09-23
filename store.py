"""Saved investigations on disk."""
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from config import RobinConfig

logger = logging.getLogger(__name__)

DEFAULT_INVESTIGATIONS_DIR = "investigations"

# Named in the save-failure warning. Keep it equal to the heading in
# TROUBLESHOOTING.md that explains the fix.
TROUBLESHOOTING_SECTION = "Saved investigations fail with permission denied on Linux"

FILENAME_PREFIX = "investigation_"
FILENAME_GLOB = FILENAME_PREFIX + "*.json"


def resolve_dir(investigations_dir=None, cfg: Optional[RobinConfig] = None) -> Path:
    """The directory investigations are written to and read from."""
    if investigations_dir:
        return Path(investigations_dir)
    cfg = cfg if cfg is not None else RobinConfig.from_env()
    return Path(cfg.investigations_dir or DEFAULT_INVESTIGATIONS_DIR)


def _as_record(investigation) -> dict:
    """The JSON body for a `pipeline.Investigation` or a plain mapping."""
    to_record = getattr(investigation, "to_record", None)
    if callable(to_record):
        return dict(to_record())
    return dict(investigation)


def _candidate_names():
    """`investigation_<stamp>.json`, then `_1`, `_2`, ... for the same second."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    yield "{}{}.json".format(FILENAME_PREFIX, stamp)
    suffix = 1
    while True:
        yield "{}{}_{}.json".format(FILENAME_PREFIX, stamp, suffix)
        suffix += 1


def _write_new_file(directory: Path, body: str) -> str:
    """Write `body` to the first free candidate name and return that name.

    Each name is claimed with an exclusive create (`open(..., "x")`), so two
    saves in the same second never write the same file.
    """
    for name in _candidate_names():
        try:
            with (directory / name).open("x", encoding="utf-8") as handle:
                handle.write(body)
        except FileExistsError:
            continue
        return name


def save_investigation(investigation, investigations_dir=None,
                       cfg: Optional[RobinConfig] = None):
    """Write an investigation to disk and return it with `saved_as` set.

    An OSError does not raise: it logs one warning naming the TROUBLESHOOTING
    entry, and the investigation comes back with `saved_as` unset.
    """
    directory = resolve_dir(investigations_dir, cfg)
    record = _as_record(investigation)
    record.setdefault("timestamp", datetime.now().isoformat())

    try:
        directory.mkdir(parents=True, exist_ok=True)
        name = _write_new_file(directory, json.dumps(record, indent=2))
    except OSError as exc:
        logger.warning(
            "Could not save the investigation to %s (%s). The investigation is "
            'intact in this session. See "%s" in TROUBLESHOOTING.md.',
            directory, exc, TROUBLESHOOTING_SECTION,
        )
        return investigation

    if hasattr(investigation, "saved_as"):
        investigation.saved_as = name
    elif isinstance(investigation, dict):
        investigation["saved_as"] = name
    return investigation


_FILENAME_RE = re.compile(
    r"^" + re.escape(FILENAME_PREFIX) + r"(\d{8}_\d{6})(?:_(\d+))?\.json$")


def _newest_first_key(path: Path):
    """Sort key: the save's timestamp, then its collision suffix as a number.

    A string sort would put `_9` after `_11`. The unsuffixed first save of a
    second ranks below `_1`; a name off the pattern sorts by its text, suffix -1.
    """
    match = _FILENAME_RE.match(path.name)
    if match:
        return (match.group(1), int(match.group(2) or 0))
    return (path.stem[len(FILENAME_PREFIX):], -1)


def load_investigations(investigations_dir=None,
                        cfg: Optional[RobinConfig] = None) -> List[dict]:
    """Every saved investigation, newest first, each carrying `_filename`.

    A file that cannot be read or parsed is skipped, so one bad file does not
    empty the list.
    """
    directory = resolve_dir(investigations_dir, cfg)
    try:
        paths = sorted(directory.glob(FILENAME_GLOB), key=_newest_first_key, reverse=True)
    except OSError as exc:
        logger.warning("Could not list %s (%s).", directory, exc)
        return []

    investigations = []
    for path in paths:
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            logger.debug("Skipping unreadable investigation %s: %s", path.name, exc)
            continue
        if not isinstance(data, dict):
            continue
        data["_filename"] = path.name
        investigations.append(data)
    return investigations
