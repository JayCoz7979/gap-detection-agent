"""Fail if the Railway redeploy helper grows a credential literal again."""
from __future__ import annotations

import ast
import importlib.util
import os
import re
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "fixes" / "railway_redeploy.py"
ENV_EXAMPLE = ROOT / ".env.example"

_CREDENTIAL_NAME = re.compile(r"(?i)token|secret|password|api[_-]?key")
_TOKEN_LIKE_LITERAL = re.compile(
    r"(?i)(token|secret|password|api[_-]?key).{0,80}['\"][A-Za-z0-9_+/=-]{20,}['\"]"
)
_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _looks_like_credential(value: str) -> bool:
    """True for a token-shaped literal, false for an error sentence."""
    if not value or any(ch.isspace() for ch in value) or value.startswith(("http://", "https://")):
        return False
    return bool(_UUID.fullmatch(value) or len(value) >= 12)


def _load_helper():
    spec = importlib.util.spec_from_file_location("railway_redeploy_under_test", HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load railway redeploy helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RailwayTokenLiteralTests(unittest.TestCase):
    def test_helper_has_no_token_like_literal(self) -> None:
        source = HELPER.read_text(encoding="utf-8")
        hits = [
            lineno
            for lineno, line in enumerate(source.splitlines(), 1)
            if _TOKEN_LIKE_LITERAL.search(line)
        ]
        self.assertEqual(hits, [], f"token-like literal in {HELPER.name} on lines {hits}")

        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if not isinstance(node.value, ast.Constant):
                    continue
                if not isinstance(node.value.value, str) or not _looks_like_credential(node.value.value):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name) and _CREDENTIAL_NAME.search(target.id):
                        self.fail(f"credential literal assigned on line {node.lineno}")
            if not isinstance(node, ast.Call) or len(node.args) < 2:
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr not in {"get", "getenv"}:
                continue
            name, default = node.args[0], node.args[1]
            if not isinstance(name, ast.Constant) or not isinstance(name.value, str):
                continue
            if not _CREDENTIAL_NAME.search(name.value):
                continue
            if (
                isinstance(default, ast.Constant)
                and isinstance(default.value, str)
                and _looks_like_credential(default.value)
            ):
                self.fail(f"non-empty credential default on line {node.lineno}")

    def test_missing_token_fails_closed_without_request(self) -> None:
        module = _load_helper()
        env = os.environ.copy()
        env.pop("RAILWAY_TOKEN", None)
        with patch.dict(os.environ, env, clear=True):
            with patch.object(module.httpx, "post") as post:
                ok, message = module.redeploy("Gap Detection")
        self.assertFalse(ok)
        self.assertEqual(message, module._MISSING_TOKEN)
        self.assertNotIn("Bearer", message)
        self.assertIsNone(re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-", message))
        post.assert_not_called()

    def test_blank_token_fails_closed_without_request(self) -> None:
        module = _load_helper()
        for blank in ("", "   "):
            with self.subTest(blank=blank):
                with patch.dict(os.environ, {"RAILWAY_TOKEN": blank}, clear=False):
                    with patch.object(module.httpx, "post") as post:
                        ok, message = module.redeploy("Gap Detection")
                self.assertFalse(ok)
                self.assertEqual(message, module._MISSING_TOKEN)
                post.assert_not_called()

    def test_configured_token_is_sent(self) -> None:
        module = _load_helper()
        response = MagicMock()
        response.json.return_value = {"data": {"serviceInstanceRedeploy": True}}
        with patch.dict(os.environ, {"RAILWAY_TOKEN": "abc"}, clear=False):
            with patch.object(module.httpx, "post", return_value=response) as post:
                ok, message = module.redeploy("Gap Detection")
        self.assertTrue(ok)
        self.assertNotIn("abc", message)
        headers = post.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer abc")

    def test_env_example_has_names_only(self) -> None:
        for lineno, line in enumerate(ENV_EXAMPLE.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            name, sep, value = line.partition("=")
            self.assertTrue(sep, f".env.example:{lineno} is not NAME=")
            self.assertRegex(name, r"^[A-Z][A-Z0-9_]*$")
            self.assertEqual(value, "", f".env.example:{lineno} has a value")
        names = {
            line.split("=", 1)[0]
            for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        self.assertIn("RAILWAY_TOKEN", names)


if __name__ == "__main__":
    unittest.main()
