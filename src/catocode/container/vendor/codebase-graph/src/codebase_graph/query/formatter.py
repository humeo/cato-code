"""Output formatting for query results."""

import json


def format_context_text(result: dict) -> str:
    """Format context query result as human-readable text."""
    if result.get("ambiguous"):
        lines = [f"Ambiguous query: {result['query']}"]
        for match in result.get("matches", []):
            lines.append(
                f"  {match['qualified_name']} ({match['kind']}) "
                f"{match['file']}:{match['line_start']}-{match['line_end']}"
            )
        return "\n".join(lines)

    symbol = result["symbol"]
    lines = []

    lines.append(f"── Symbol: {symbol['name']} {'─' * max(1, 50 - len(symbol['name']))}")
    lines.append(f"  Kind:      {symbol['kind']}")
    lines.append(
        f"  File:      {symbol['file']}:{symbol['line_start']}-{symbol['line_end']}"
    )
    if symbol.get("signature"):
        lines.append(f"  Signature: {symbol['signature']}")

    callers = result.get("callers", [])
    if callers:
        lines.append(f"\n── Called by ({len(callers)}) {'─' * 40}")
        for caller in callers:
            loc = f"{caller.get('file_path', '?')}:{caller.get('line', '?')}"
            lines.append(f"  {caller['name']:<25s} {loc}")

    callees = result.get("callees", [])
    if callees:
        lines.append(f"\n── Calls ({len(callees)}) {'─' * 43}")
        for callee in callees:
            loc = (
                f"{callee.get('file_path', '?')}:{callee.get('line', '?')}"
                if callee.get("file_path")
                else "unresolved"
            )
            lines.append(f"  {callee['name']:<25s} {loc}")

    imports = result.get("imports", [])
    if imports:
        lines.append(f"\n── Imports ({len(imports)}) {'─' * 41}")
        for imported in imports:
            loc = (
                f"{imported.get('file_path', '?')}:{imported.get('line', '?')}"
                if imported.get("file_path")
                else "unresolved"
            )
            lines.append(f"  {imported['name']:<25s} {loc}")

    key_files = result.get("key_files", [])
    if key_files:
        lines.append(f"\n── Key Files {'─' * 42}")
        for file_info in key_files:
            lines.append(f"  {file_info['path']}")

    return "\n".join(lines)


def format_json(data: dict | list) -> str:
    """Format any data as JSON."""
    return json.dumps(data, indent=2, default=str)
