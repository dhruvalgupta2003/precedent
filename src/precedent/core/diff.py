"""Facts about a change: which files, and what the added lines import or depend on (docs/spec.md §7).

Regex, not a parser: good enough to find imports and dependency lines, and cheap enough for a hook.
Only added lines count, so removing a dependency is never a conflict.
"""

import re
from dataclasses import dataclass
from typing import NamedTuple

JS_IMPORT = re.compile(r"""^\s*import\s+(?:(?P<names>[\w*\s{},$]+?)\s+from\s+)?['"](?P<module>[^'"]+)['"]""")
JS_CALL = re.compile(r"""\b(?:require|import)\(\s*['"]([^'"]+)['"]\s*\)""")
PY_IMPORT = re.compile(r"^\s*import\s+([\w.]+)")
PY_FROM = re.compile(r"^\s*from\s+([\w.]+)\s+import\s+(.+)")
PACKAGE_JSON_DEP = re.compile(r'^\s*"(@?[\w.-]+(?:/[\w.-]+)?)"\s*:\s*"(?:[\^~<>=*\d]|workspace:|npm:|latest)')
REQUIREMENT = re.compile(r"^\s*([A-Za-z0-9][\w.-]*)\s*(?:[<>=~!;\[]|$)")
NOT_PACKAGES = {"name", "version", "node", "npm", "yarn", "pnpm"}
DOCS = (".md", ".mdx", ".rst", ".adoc", ".txt")  # code examples in docs are not code


class Change(NamedTuple):
    path: str
    added: tuple[str, ...]


@dataclass(frozen=True)
class Facts:
    paths: frozenset[str]
    packages: frozenset[str]
    imported: frozenset[tuple[str, str]]  # (module, name), e.g. ("react", "FC")
    text: str  # every added line, for symbol and pattern matches


def changes(diff: str) -> list[Change]:
    """Each file in a unified diff with its added lines."""
    files: dict[str, list[str]] = {}
    current: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = files.setdefault(line[4:].removeprefix("b/"), [])
        elif line.startswith("+"):
            current.append(line[1:])
    return [Change(path, tuple(lines)) for path, lines in files.items()]


def facts(change_list: list[Change]) -> Facts:
    packages: set[str] = set()
    imported: set[tuple[str, str]] = set()
    code = [c for c in change_list if _manifest_pattern(c.path) or not c.path.lower().endswith(DOCS)]
    for change in code:
        manifest = _manifest_pattern(change.path)
        for line in change.added:
            packages |= _imports(line, imported)
            if manifest and (m := manifest.match(line)) and m[1] not in NOT_PACKAGES:
                packages.add(m[1].lower() if manifest is REQUIREMENT else m[1])
    text = "\n".join(line for change in code for line in change.added)
    return Facts(frozenset(c.path for c in change_list), frozenset(packages), frozenset(imported), text)


def _manifest_pattern(path: str) -> re.Pattern[str] | None:
    name = path.rsplit("/", 1)[-1]
    if name == "package.json":
        return PACKAGE_JSON_DEP
    return REQUIREMENT if name.startswith("requirements") and name.endswith(".txt") else None


def _imports(line: str, imported: set[tuple[str, str]]) -> set[str]:
    """Packages this line imports; named imports are added to `imported`."""
    if m := JS_IMPORT.match(line):
        for name in re.findall(r"(\w+)(?:\s+as\s+\w+)?", (m["names"] or "").replace("* as", "")):
            imported.add((m["module"].lower(), name))
        return _package({m["module"]})
    if m := PY_FROM.match(line):
        imported.update((m[1].lower(), name) for name in re.findall(r"(\w+)(?:\s+as\s+\w+)?", m[2]))
        return _package({m[1].split(".")[0]})
    if m := PY_IMPORT.match(line):
        return {m[1].split(".")[0]}
    return _package(set(JS_CALL.findall(line)))


def _package(modules: set[str]) -> set[str]:
    """'@scope/pkg/sub' → '@scope/pkg', 'pkg/sub' → 'pkg'; relative paths aren't packages."""
    names = set()
    for module in modules:
        if module.startswith("."):
            continue
        parts = module.split("/")
        names.add("/".join(parts[:2]) if module.startswith("@") else parts[0])
    return names
