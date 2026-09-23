"""The image, the entrypoint and the registry entry: only what the product depends on."""
import ast
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOLUME = "robin-investigations:/app/investigations"


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


_GLOB = {"\\*\\*/": "(?:.*/)?", "\\*\\*": ".*", "\\*": "[^/]*", "\\?": "[^/]"}


def excluded_by_dockerignore(path):
    """True when Docker leaves `path` out of the build context.

    Each pattern is tried against the path and its parents, `*` stopping at a
    slash as in Docker's matcher; the last match decides and `!` re-includes.
    """
    parts = path.split("/")
    candidates = ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]
    excluded = False
    for line in read(".dockerignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pattern = re.sub(r"\\\*\\\*/|\\\*\\\*|\\\*|\\\?", lambda m: _GLOB[m.group()],
                         re.escape(line.lstrip("!").strip("/")))
        if any(re.fullmatch(pattern, candidate) for candidate in candidates):
            excluded = not line.startswith("!")
    return excluded


def ui_assets():
    """Every literal path ui.py hands to st.image or st.logo."""
    return [node.args[0].value for node in ast.walk(ast.parse(read("ui.py")))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("image", "logo") and getattr(node.func.value, "id", "") == "st"
            and node.args and isinstance(node.args[0], ast.Constant)]


def mcp_mode():
    """Everything entrypoint.sh runs in mcp mode: the shared preamble and the mcp branch."""
    text = read("entrypoint.sh")
    return text[:text.index("\nfi\n", text.index('if [ "$MODE" = "mcp" ]'))]


class TheImage(unittest.TestCase):
    """What the build context ships and what the Dockerfile sets up."""

    def test_secrets_and_case_data_stay_out_and_the_example_env_and_logo_ship(self):
        for path in (".env", ".env.local", "investigations/investigation_1.json"):
            with self.subTest(path=path):
                self.assertTrue(excluded_by_dockerignore(path))
        assets = ui_assets()
        self.assertTrue(assets, "found no st.image call in ui.py")
        for path in [".env.example"] + assets:
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file(), path)
                self.assertFalse(excluded_by_dockerignore(path))

    def test_the_dockerfile_labels_the_server_and_pre_creates_robin_owned_directories(self):
        dockerfile = read("Dockerfile")
        name = json.loads(read("server.json"))["name"]
        self.assertIn('LABEL io.modelcontextprotocol.server.name="%s"' % name, dockerfile)
        after_copy = dockerfile.split("COPY --chown=robin:robin . .", 1)[1]
        for mode, directory in (("0700", "/home/robin/.tor"), ("0700", "/home/robin/.robin"),
                                ("0755", "/app/investigations")):
            with self.subTest(directory):
                self.assertIn("install -d -m %s -o robin -g robin %s " % (mode, directory),
                              after_copy)


class McpModeWritesNothingToStdout(unittest.TestCase):
    """In mcp mode stdout is the JSON-RPC transport."""

    def test_every_echo_goes_to_stderr(self):
        echoes = [line.strip() for line in mcp_mode().splitlines()
                  if line.strip().startswith("echo ")]
        self.assertTrue(echoes)
        for line in echoes:
            with self.subTest(line):
                self.assertTrue(line.endswith(">&2"))

    def test_tor_and_the_model_warm_up_write_to_stderr_in_the_background(self):
        branch = mcp_mode().split('if [ "$MODE" = "mcp" ]', 1)[1]
        self.assertIn("tor_with_log >&2 &", branch)
        self.assertNotRegex(branch, r"(?m)^\s*tor(_with_log)?\s*&")
        self.assertIn('model_registry.refresh(verbose=True)" >&2', branch)
        self.assertRegex(branch, r"(?m)^\s*\) &$")
        self.assertNotIn("wait_for_bootstrap", branch)


class TheMcpPackage(unittest.TestCase):
    """The pinned SDK and the registry entry."""

    def test_requirements_pins_mcp_to_an_exact_version(self):
        self.assertRegex(read("requirements.txt"), r"(?m)^mcp==\d+\.\d+\.\d+\s*$")

    def test_server_json_is_publishable_and_mounts_the_volume(self):
        for package in json.loads(read("server.json"))["packages"]:
            self.assertEqual(package["registryType"], "oci")
            for field in ("registryBaseUrl", "version", "fileSha256"):
                self.assertNotIn(field, package)
            self.assertRegex(package["identifier"], r"^docker\.io/apurvsg/robin:v\d+\.\d+$")
            volumes = [a for a in package["runtimeArguments"] if a.get("name") == "-v"]
            self.assertEqual([(a["type"], a["value"]) for a in volumes], [("named", VOLUME)])


if __name__ == "__main__":
    unittest.main()
