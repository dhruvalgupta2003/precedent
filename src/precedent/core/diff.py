"""Facts about a change: which files, and what the added lines import or depend on (docs/spec.md §7).

Regex, not a parser: good enough to find imports and dependency lines, and cheap enough for a hook.
Only net new lines count: removing a dependency is never a conflict, and a line moved within the same
change is not new usage.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import NamedTuple

JS_IMPORT = re.compile(r"""^\s*import\s+(?:(?P<names>[\w*\s{},$]+?)\s+from\s+)?['"](?P<module>[^'"]+)['"]""")
JS_REEXPORT = re.compile(r"""^\s*export\s+(?:type\s+)?(?:\*(?:\s+as\s+\w+)?|\{[^}]*\})\s+from\s+['"]([^'"]+)['"]""")
JS_CALL = re.compile(r"""\b(?:require|import)\(\s*['"]([^'"]+)['"]\s*\)""")
PY_IMPORT = re.compile(r"^\s*import\s+([\w.]+)")
PY_FROM = re.compile(r"^\s*from\s+([\w.]+)\s+import\s+(.+)")
PACKAGE_JSON_DEP = re.compile(r'^\s*"(@?[\w.-]+(?:/[\w.-]+)?)"\s*:\s*"(?:[\^~<>=*\d]|workspace:|npm:|latest)')
REQUIREMENT = re.compile(r"^\s*([A-Za-z0-9][\w.-]*)\s*(?:[<>=~!;\[]|$)")
# Strings and comments aren't code: a log line or a TODO that names a symbol isn't using it.
NOT_CODE = re.compile(r"""//[^\n]*|/\*.*?\*/|#[^\n]*|'(?:\\.|[^'\\\n])*'|"(?:\\.|[^"\\\n])*"|`(?:\\.|[^`\\])*`""", re.S)
EXPORT_AS_DEFAULT = re.compile(r"export\s*\{\s*(\w+)\s+as\s+default\s*\}")  # same thing as `export default X`
NOT_PACKAGES = {"name", "version", "node", "npm", "yarn", "pnpm"}
DOCS = (".md", ".mdx", ".rst", ".adoc", ".txt")  # code examples in docs are not code


class Change(NamedTuple):
    path: str
    added: tuple[str, ...]
    removed: tuple[str, ...] = ()


@dataclass(frozen=True)
class Facts:
    paths: frozenset[str]
    packages: frozenset[str]
    imported: frozenset[tuple[str, str]]  # (module, name), e.g. ("react", "FC")
    text: str  # every net new line, for config and plan matches
    code: str = ""  # the same without strings and comments, in canonical form: for symbol matches
    aliases: dict[str, str] = field(default_factory=dict)  # local name → module: `import * as R from 'react'`


def changes(diff: str) -> list[Change]:
    """Each file in a unified diff with its added and removed lines."""
    files: dict[str, tuple[list[str], list[str]]] = {}
    added: list[str] = []
    removed: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+++ "):
            added, removed = files.setdefault(line[4:].removeprefix("b/"), ([], []))
        elif line.startswith("+"):
            added.append(line[1:])
        elif line.startswith("-") and not line.startswith("--- "):
            removed.append(line[1:])
    return [Change(path, tuple(a), tuple(r)) for path, (a, r) in files.items()]


def facts(change_list: list[Change]) -> Facts:
    code_changes = [c for c in _net_new(change_list) if _manifest_pattern(c.path) or not c.path.lower().endswith(DOCS)]
    packages: set[str] = set()
    imported: set[tuple[str, str]] = set()
    aliases: dict[str, str] = {}
    for change in code_changes:
        packages |= _packages_in(change, imported, aliases)
    text = "\n".join(line for change in code_changes for line in change.added)
    code = EXPORT_AS_DEFAULT.sub(r"export default \1", NOT_CODE.sub(" ", text))
    paths = frozenset(c.path for c in change_list)
    return Facts(paths, frozenset(packages), frozenset(imported), text, code, aliases)


def _net_new(change_list: list[Change]) -> list[Change]:
    """Drop added lines that the same change removes elsewhere: moved code is not new code."""
    removed = Counter(line.strip() for change in change_list for line in change.removed)
    result = []
    for change in change_list:
        kept = []
        for line in change.added:
            if removed[line.strip()] > 0:
                removed[line.strip()] -= 1
            else:
                kept.append(line)
        result.append(change._replace(added=tuple(kept)))
    return result


def _packages_in(change: Change, imported: set[tuple[str, str]], aliases: dict[str, str]) -> set[str]:
    manifest = _manifest_pattern(change.path)
    packages: set[str] = set()
    for line in change.added:
        packages |= _imports(line, imported, aliases)
        if manifest and (m := manifest.match(line)) and m[1] not in NOT_PACKAGES:
            packages.add(m[1].lower() if manifest is REQUIREMENT else m[1])
    return packages


def _manifest_pattern(path: str) -> re.Pattern[str] | None:
    name = path.rsplit("/", 1)[-1]
    if name == "package.json":
        return PACKAGE_JSON_DEP
    return REQUIREMENT if name.startswith("requirements") and name.endswith(".txt") else None


def _imports(line: str, imported: set[tuple[str, str]], aliases: dict[str, str]) -> set[str]:
    """Packages this line imports or re-exports; named imports and aliases are recorded too."""
    if m := JS_IMPORT.match(line):
        _record_js_names(m["names"] or "", m["module"].lower(), imported, aliases)
        return _package({m["module"]})
    if m := PY_FROM.match(line):
        imported.update((m[1].lower(), name) for name in re.findall(r"(\w+)(?:\s+as\s+\w+)?", m[2]))
        return _package({m[1].split(".")[0]})
    if m := PY_IMPORT.match(line):
        return {m[1].split(".")[0]}
    reexport = JS_REEXPORT.match(line)
    return _package(set(JS_CALL.findall(line)) | ({reexport[1]} if reexport else set()))


def _record_js_names(names: str, module: str, imported: set[tuple[str, str]], aliases: dict[str, str]) -> None:
    """`import React, { FC } from 'react'` and `import * as R from 'react'`."""
    if namespace := re.search(r"\*\s*as\s+(\w+)", names):
        aliases[namespace[1]] = module
    if default := re.match(r"\s*([A-Za-z_$][\w$]*)\s*(?:,|$)", names):
        aliases[default[1]] = module
    for name in re.findall(r"(\w+)(?:\s+as\s+\w+)?", re.sub(r"\*\s*as\s+\w+", "", names)):
        imported.add((module, name))


def _package(modules: set[str]) -> set[str]:
    """'@scope/pkg/sub' → '@scope/pkg', 'pkg/sub' → 'pkg'; relative paths aren't packages."""
    names = set()
    for module in modules:
        if module.startswith("."):
            continue
        parts = module.split("/")
        names.add("/".join(parts[:2]) if module.startswith("@") else parts[0])
    return names
