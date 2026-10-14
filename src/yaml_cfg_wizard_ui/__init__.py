"""Render a self-contained page consuming an allowlisted JSON snapshot."""

from __future__ import annotations

from importlib.resources import files
import json
import re
from string import Template
from typing import Mapping
from urllib.parse import unquote, urlsplit

__all__ = ["render_page"]
_TYPES = {"string", "boolean", "integer", "number", "null"}


def _text(value: str, name: str, limit: int) -> str:
    if not isinstance(value, str) or len(value) > limit or any(
        ord(c) < 32 and c not in "\n\t" for c in value
    ):
        raise ValueError(f"Invalid {name}")
    return value


def render_page(
    *,
    endpoint: str,
    csrf_token: str,
    title: str = "Configuration editor",
    description: str = "Edit allowlisted scalar overrides.",
    saved_message: str = "Saved.",
    fields: Mapping[str, Mapping] | None = None,
    script_nonce: str = "",
) -> str:
    """Return HTML; the host owns authentication, allowlisting and HTTP routing.

    ``fields`` maps paths to optional ``type`` (scalar name or list of names),
    ``nullable`` and ``maxLength`` metadata. Null-only rows need explicit types
    to become editable. No configuration files or application adapters load.
    """
    if not isinstance(script_nonce, str) or len(script_nonce) > 256 or (
        script_nonce and not re.fullmatch(r"[A-Za-z0-9+/=_-]+", script_nonce)
    ):
        raise ValueError("Invalid script nonce")
    _text(endpoint, "endpoint", 2048)
    decoded = unquote(endpoint)
    parts = urlsplit(endpoint)
    if (
        not endpoint.startswith("/") or endpoint.startswith("//")
        or decoded.startswith("//") or "\\" in decoded
        or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in decoded)
        or parts.scheme or parts.netloc or parts.query or parts.fragment
        or "?" in endpoint or "#" in endpoint
    ):
        raise ValueError("Endpoint must be a same-origin root-relative path")
    _text(csrf_token, "CSRF token", 4096)
    if not csrf_token or any(ord(c) < 33 or ord(c) > 126 for c in csrf_token):
        raise ValueError("Invalid CSRF token")
    metadata = {}
    if fields is not None:
        if not isinstance(fields, Mapping) or len(fields) > 1000:
            raise ValueError("Invalid fields")
        for path, spec in fields.items():
            _text(path, "field path", 1024)
            if not path or not isinstance(spec, Mapping) or set(spec) - {"type", "nullable", "maxLength"}:
                raise ValueError("Invalid field metadata")
            item = dict(spec)
            types = item.get("type")
            if types is not None:
                types = [types] if isinstance(types, str) else types
                if not isinstance(types, list) or not types or any(
                    not isinstance(t, str) or t not in _TYPES for t in types
                ) or len(set(types)) != len(types):
                    raise ValueError("Invalid field type")
                item["type"] = types
            if "nullable" in item and not isinstance(item["nullable"], bool):
                raise ValueError("Invalid nullable metadata")
            if "maxLength" in item and (
                type(item["maxLength"]) is not int or not 0 <= item["maxLength"] <= 1000000
            ):
                raise ValueError("Invalid maxLength metadata")
            metadata[path] = item
    config = {
        "endpoint": endpoint,
        "csrfToken": csrf_token,
        "title": _text(title, "title", 512),
        "description": _text(description, "description", 8192),
        "savedMessage": _text(saved_message, "saved message", 8192),
        "fields": metadata,
    }
    encoded = json.dumps(config, ensure_ascii=True, allow_nan=False)
    for char, escaped in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026")):
        encoded = encoded.replace(char, escaped)
    assets = files(__package__).joinpath("assets")
    return Template(assets.joinpath("page.html").read_text(encoding="utf-8")).substitute(
        css=assets.joinpath("editor.css").read_text(encoding="utf-8"),
        js=assets.joinpath("editor.js").read_text(encoding="utf-8"),
        config=encoded,
        nonce=script_nonce,
    )
