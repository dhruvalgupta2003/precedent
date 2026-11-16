"""Reviewed YAML files (precedent.yaml, checks, promotions, places), read so nothing can hide, explode or crash in them.

`parse` works on bytes, so the same rules apply to a file on disk and to a blob read from a git tree.
"""

from pathlib import Path

import yaml
from yaml.composer import ComposerError

from precedent.core.errors import KnowledgeError

MAX_BYTES = 1_048_576  # a hand-written decisions file is far smaller; anything bigger is a mistake or an attack
SHOWN = 80  # characters of file text an error message may echo
MERGE = "tag:yaml.org,2002:merge"


class _StrictLoader(yaml.SafeLoader):
    """Safe YAML with one reading only: no aliases (one line could expand into gigabytes), no merge keys (`<<` could
    hide a block), keys that are text (`on` and `true` would both become True), and no key written twice."""

    def compose_node(self, parent: yaml.Node | None, index: object) -> yaml.Node | None:
        if self.check_event(yaml.AliasEvent):
            raise ComposerError(None, None, "anchors and aliases aren't allowed", self.peek_event().start_mark)
        return super().compose_node(parent, index)

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict:
        seen: set[str] = set()
        for key_node, _ in node.value:
            if key_node.tag == MERGE:
                raise yaml.MarkedYAMLError(problem="merge keys (<<) aren't allowed", problem_mark=key_node.start_mark)
            key = self.construct_object(key_node)
            if not isinstance(key, str):
                problem = f"keys must be text; put quotes around {shown(key_node.value)}"
                raise yaml.MarkedYAMLError(problem=problem, problem_mark=key_node.start_mark)
            if key in seen:
                raise yaml.MarkedYAMLError(problem=f"{shown(key)} is written twice", problem_mark=key_node.start_mark)
            seen.add(key)
        return super().construct_mapping(node, deep)


def read(path: Path, name: str) -> bytes:
    """A reviewed file from disk: a regular file (never a link, which could lead outside the repo, nor a pipe, which
    would hang), within the size limit."""
    if path.is_symlink():
        raise KnowledgeError(f"{name} must be a regular file, not a link")
    if not path.is_file():
        raise KnowledgeError(f"{name} must be a regular file")
    if path.stat().st_size > MAX_BYTES:
        raise KnowledgeError(f"{name} is too large (the limit is {MAX_BYTES} bytes)")
    return path.read_bytes()


def parse(raw: bytes, name: str) -> object:
    """The data, or a KnowledgeError that names the file and line. Never a crash: a crafted file must be refused, not
    break a check run."""
    if len(raw) > MAX_BYTES:
        raise KnowledgeError(f"{name} is too large (the limit is {MAX_BYTES} bytes)")
    try:
        return yaml.load(raw.decode("utf-8"), Loader=_StrictLoader)  # noqa: S506 (a SafeLoader)
    except UnicodeDecodeError as exc:
        raise KnowledgeError(f"{name} is not UTF-8 text") from exc
    except yaml.MarkedYAMLError as exc:
        line = f": line {exc.problem_mark.line + 1}" if exc.problem_mark else ""
        raise KnowledgeError(f"{name}{line}: {shown(exc.problem or 'not valid YAML')}") from exc
    except yaml.YAMLError as exc:
        raise KnowledgeError(f"{name} is not valid YAML") from exc
    except RecursionError as exc:
        raise KnowledgeError(f"{name} is nested too deeply") from exc
    except (ValueError, OverflowError, TypeError) as exc:
        raise KnowledgeError(f"{name} has a value that can't be read (an impossible date, for example)") from exc


def shown(value: object) -> str:
    """File text as an error message may show it: control characters spelled out, at most 80 characters."""
    text = "".join(c if c.isprintable() else repr(c)[1:-1] for c in str(value))
    return text if len(text) <= SHOWN else f"{text[: SHOWN - 1]}…"
