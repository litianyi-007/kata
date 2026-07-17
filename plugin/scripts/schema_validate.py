#!/usr/bin/env python3
"""Validate a wiki's SCHEMA.md against plugin/schema/wiki-schema.json.

Pure stdlib — implements the subset of JSON Schema that wiki-schema.json uses
(type, enum, required, pattern, minimum, additionalProperties, items, allOf,
anyOf, if/then). No third-party deps so the validator runs everywhere a skill
runs.

Usage:
    schema_validate.py --wiki <path>                    # validate wiki SCHEMA.md
    schema_validate.py --file path/to/SCHEMA.md         # explicit path
    schema_validate.py --validate-plugins-yaml <file>   # also runs on .wiki-plugins.yaml
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from wiki_lib import emit, find_wiki_root, load_schema, _parse_yaml_block

# Resolved *within the plugin tree* (parents[1] = plugin/, from
# plugin/scripts/schema_validate.py) — NOT parents[2] (repo root). Marketplace
# installs package only `source="./plugin"` (see .claude-plugin/marketplace.json),
# so anything outside plugin/ never reaches ~/.claude/plugins/cache/kata/kata/<ver>/.
# Before this fix, SCHEMA_FILE pointed at parents[2]/"schema"/... (the repo-root
# schema/ dir), which worked in a dev checkout (repo root two levels up) but
# resolved to a nonexistent path once installed from the marketplace (two
# levels up from the *installed* script is the plugin-cache's `kata/` owner
# dir, not the repo root) — schema_validate.py crashed with FileNotFoundError
# for every installed user. Moving wiki-schema.json into plugin/schema/ makes
# it single-sourced and always packaged alongside the script that reads it.
SCHEMA_FILE = Path(__file__).resolve().parents[1] / "schema" / "wiki-schema.json"


class ValidationError(Exception):
    pass


def validate(data, schema, path: str = "$") -> list[str]:
    errors: list[str] = []
    if "$ref" in schema:
        # Local refs only: #/$defs/foo
        ref = schema["$ref"]
        if ref.startswith("#/"):
            target = _root_schema()
            for part in ref.lstrip("#/").split("/"):
                target = target.get(part, {})
            return validate(data, target, path)

    if "type" in schema:
        if not _check_type(data, schema["type"]):
            errors.append(f"{path}: expected type {schema['type']}, got {type(data).__name__}")
            return errors  # don't cascade

    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: value {data!r} not in enum {schema['enum']}")

    if "const" in schema and data != schema["const"]:
        errors.append(f"{path}: value {data!r} != const {schema['const']!r}")

    if "pattern" in schema and isinstance(data, str):
        if not re.search(schema["pattern"], data):
            errors.append(f"{path}: {data!r} does not match pattern {schema['pattern']!r}")

    if "minimum" in schema and isinstance(data, (int, float)):
        if data < schema["minimum"]:
            errors.append(f"{path}: {data} < minimum {schema['minimum']}")

    if "minLength" in schema and isinstance(data, str):
        if len(data) < schema["minLength"]:
            errors.append(f"{path}: length {len(data)} < minLength {schema['minLength']}")

    if "minItems" in schema and isinstance(data, list):
        if len(data) < schema["minItems"]:
            errors.append(f"{path}: {len(data)} items < minItems {schema['minItems']}")

    if "uniqueItems" in schema and schema["uniqueItems"] and isinstance(data, list):
        if len(set(map(_hashable, data))) != len(data):
            errors.append(f"{path}: items not unique")

    if isinstance(data, dict):
        if "required" in schema:
            for req in schema["required"]:
                if req not in data:
                    errors.append(f"{path}: missing required field {req!r}")
        if "properties" in schema:
            for k, sub in schema["properties"].items():
                if k in data:
                    errors.extend(validate(data[k], sub, f"{path}.{k}"))
        if schema.get("additionalProperties") is False:
            allowed = set(schema.get("properties", {}).keys())
            for k in data:
                if k not in allowed:
                    errors.append(f"{path}: unexpected property {k!r}")
        if "if" in schema:
            cond_errs = validate(data, schema["if"], path)
            if not cond_errs and "then" in schema:
                errors.extend(validate(data, schema["then"], path))
            elif cond_errs and "else" in schema:
                errors.extend(validate(data, schema["else"], path))

    if isinstance(data, list) and "items" in schema:
        for i, item in enumerate(data):
            errors.extend(validate(item, schema["items"], f"{path}[{i}]"))

    if "allOf" in schema:
        for sub in schema["allOf"]:
            errors.extend(validate(data, sub, path))

    if "anyOf" in schema:
        any_errors = []
        for sub in schema["anyOf"]:
            sub_errs = validate(data, sub, path)
            if not sub_errs:
                any_errors = []
                break
            any_errors.append(sub_errs)
        if any_errors:
            errors.append(f"{path}: did not match any of {len(schema['anyOf'])} alternatives")

    return errors


_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


def _check_type(data, t) -> bool:
    if isinstance(t, list):
        return any(_check_type(data, sub) for sub in t)
    if t == "integer" and isinstance(data, bool):
        return False
    py = _TYPE_MAP.get(t)
    return isinstance(data, py) if py else True


def _hashable(v):
    try:
        hash(v)
        return v
    except TypeError:
        return json.dumps(v, sort_keys=True, default=str)


_ROOT_SCHEMA: dict | None = None


def _root_schema() -> dict:
    global _ROOT_SCHEMA
    if _ROOT_SCHEMA is None:
        _ROOT_SCHEMA = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    return _ROOT_SCHEMA


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--wiki", default=None)
    p.add_argument("--file", default=None)
    p.add_argument("--validate-plugins-yaml", default=None,
                   dest="plugins_yaml")
    args = p.parse_args()

    schema_doc = _root_schema()
    errors: list[str] = []

    if args.plugins_yaml:
        text = Path(args.plugins_yaml).read_text(encoding="utf-8")
        data = _parse_yaml_block(text)
        plugins = data.get("plugins", [])
        for i, plugin in enumerate(plugins):
            errors.extend(_validate_plugin(plugin, f"plugins[{i}]", schema_doc))

    if args.wiki or args.file or not args.plugins_yaml:
        if args.file:
            schema_md = Path(args.file)
            wiki_root = schema_md.parent
        else:
            wiki_root = find_wiki_root(args.wiki)
            schema_md = wiki_root / "SCHEMA.md"
        if not schema_md.exists():
            emit({"valid": False, "error": f"SCHEMA.md not found at {schema_md}"})
            return 2
        cfg = load_schema(wiki_root)
        # Surface YAML subset-parser failures explicitly: previously
        # load_schema swallowed parse errors and the validator would then
        # complain about "missing required field" when the real story was
        # "your block scalar / anchor / alias is unsupported". Now the
        # reason shows up in the error list verbatim.
        for pe in cfg.pop("_parse_errors", []) or []:
            errors.append(f"yaml-parse: {pe}")
        errors.extend(validate(cfg, schema_doc, "$"))
        errors.extend(_cross_field_checks(cfg))

    emit({
        "valid": len(errors) == 0,
        "errors": errors,
        "error_count": len(errors),
    })
    return 0 if not errors else 1


def _cross_field_checks(cfg: dict) -> list[str]:
    """Semantic rules across multiple fields. Run after structural validation."""
    errors: list[str] = []

    # Rule 1: active_days < archived_days
    mt = cfg.get("memory_tiers")
    if isinstance(mt, dict) and mt.get("enabled", True):
        a = mt.get("active_days")
        b = mt.get("archived_days")
        if isinstance(a, int) and isinstance(b, int) and a >= b:
            errors.append(
                f"$.memory_tiers: active_days ({a}) must be < archived_days "
                f"({b}); otherwise the archived tier is empty by definition.")

    # Rule 2: custom_dimensions.name unique
    dims = cfg.get("custom_dimensions") or []
    if isinstance(dims, list):
        names = [d.get("name") for d in dims if isinstance(d, dict)]
        seen = set()
        for n in names:
            if n in seen:
                errors.append(f"$.custom_dimensions: duplicate dimension name {n!r}")
            seen.add(n)

    # Rule 3: custom_dimensions.applies_to references declared categories
    declared = set()
    for cat in cfg.get("categories") or []:
        if isinstance(cat, dict) and "name" in cat:
            declared.add(cat["name"])
    if declared:
        for i, d in enumerate(dims):
            if not isinstance(d, dict):
                continue
            applies = d.get("applies_to")
            if isinstance(applies, list):
                for cat in applies:
                    if cat not in declared:
                        errors.append(
                            f"$.custom_dimensions[{i}].applies_to: "
                            f"{cat!r} is not a declared category "
                            f"(known: {sorted(declared)})")

    # Rules 4-5: dreaming block sanity (forward compat with v1.6)
    dr = cfg.get("dreaming")
    if isinstance(dr, dict):
        weights = dr.get("weights")
        if isinstance(weights, dict):
            for k, v in weights.items():
                if isinstance(v, (int, float)) and v < 0:
                    errors.append(
                        f"$.dreaming.weights.{k}: must be >= 0, got {v}")
        thr = dr.get("confidence_threshold")
        if isinstance(thr, (int, float)) and not (0 <= thr <= 1):
            errors.append(
                f"$.dreaming.confidence_threshold: must be in [0, 1], got {thr}")

    # Rule 6 (PRD-v1.8-sync §12): sync.enabled requires wiki_id
    sync_cfg = cfg.get("sync")
    if isinstance(sync_cfg, dict) and sync_cfg.get("enabled") is True:
        if not cfg.get("wiki_id"):
            errors.append(
                "$.sync: enabled=true requires $.wiki_id (UUID v4) for "
                "cross-machine identity check; run `wiki-init --refresh-id` "
                "to generate one, or set sync.enabled to false")

    return errors


def _validate_plugin(plugin: dict, path: str, root_schema: dict) -> list[str]:
    plugin_schema = root_schema["$defs"]["external_plugin"]
    errors = validate(plugin, plugin_schema, path)
    # Extra security check on argv tokens
    forbidden = {";", "|", "&", "`", "$(", "$<", ">", "<", "&&", "||"}
    for i, token in enumerate(plugin.get("argv", []) or []):
        for f in forbidden:
            if f in token:
                errors.append(
                    f"{path}.argv[{i}]: token {token!r} contains forbidden "
                    f"shell metachar {f!r} — argv tokens are passed to "
                    f"execve, not a shell, but this is likely a misconfig.")
    return errors


if __name__ == "__main__":
    raise SystemExit(main())
