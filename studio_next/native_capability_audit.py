"""Read-only, source-grounded native editor capability exposure audit.

A registered native tool, a host-granted tool and a tested creative operation
are three different facts. This audits only the first two. No callable API,
permission, installed model, remote service or professional quality is inferred.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from collections.abc import Mapping


def audit_native_coverage(advertised, grants):
    """Compare the COMPLETE live native tools/list to exact trusted host grants.

    Never assume a disallowed tool is safe just because its name begins with
    'get' or 'list'. No missing operation is executed or automatically granted.
    """
    if not isinstance(advertised, (list, tuple)) or not advertised:
        raise ValueError("Complete native tool catalog is required")
    if not isinstance(grants, Mapping) or any(
            not isinstance(name, str) or not name or role not in ("read", "write")
            for name, role in grants.items()):
        raise ValueError("Only explicit host read/write grants can be audited")
    installed = set()
    properties = {}
    for descriptor in advertised:
        if not isinstance(descriptor, dict):
            raise ValueError("Native tools/list entries must be objects")
        name = descriptor.get("name")
        schema = descriptor.get("inputSchema", descriptor.get("input_schema"))
        if (not isinstance(name, str) or not name or
                len(name) > 160 or name in installed or
                not isinstance(schema, dict) or schema.get("type") != "object" or
                not isinstance(schema.get("properties", {}), dict)):
            raise ValueError("Native tool identity or input schema is invalid")
        # JSON Schema boolean properties are valid; None/string schemas
        # are not. Preserve source-declared free-form nested native objects.
        if any(not isinstance(value, (dict, bool))
               for value in schema.get("properties", {}).values()):
            raise ValueError("Native parameter property has an invalid schema")
        installed.add(name)
        properties[name] = len(schema.get("properties", {}))
    unknown = set(grants) - installed
    if unknown:
        raise ValueError("Host grants reference absent native operations")
    missing = sorted(installed - set(grants))
    families = Counter(name.split("_", 1)[0] for name in missing)
    return {
        "native_advertised": len(installed),
        "host_granted": len(grants),
        "host_granted_read": sum(role == "read" for role in grants.values()),
        "host_granted_write": sum(role == "write" for role in grants.values()),
        "host_ungranted": len(missing),
        "ungranted_native_names": missing,
        "ungranted_action_families": dict(sorted(families.items())),
        "schema_property_counts_for_granted": {
            name: properties[name] for name in sorted(grants)},
        "catalog_is_live_native_not_a_markdown_inventory": True,
        "no_tools_dispatched_by_this_audit": True,
        "ungranted_tools_not_automatically_exposed_to_brain": True,
        "full_native_schema_conformance_verified": False,
        "autonomous_execution_or_professional_quality_verified": False,
    }


def main(argv=None):
    """Inspect a trusted running local editor without applying any mutation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True,
                        help="Trusted literal loopback MCP URL")
    parser.add_argument("--config", required=True, type=Path,
                        help="Private host-owned editor config JSON")
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Host editor configuration must be an object")
    from .body_editor_client import LocalEditorClient
    discovered = LocalEditorClient(
        args.endpoint, allowed_tools={}).list_tools()
    result = audit_native_coverage(discovered, config.get("allowed_tools"))
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
