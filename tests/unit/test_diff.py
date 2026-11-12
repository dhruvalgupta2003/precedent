from precedent.core.diff import Change, changes, facts


def diff(path: str, *lines: str) -> str:
    return f"--- a/{path}\n+++ b/{path}\n@@ -1,1 +1,2 @@\n" + "\n".join(lines) + "\n"


def test_a_unified_diff_gives_each_file_and_only_its_added_lines():
    text = diff("src/a.ts", "+import x from 'x';", " unchanged", "-import y from 'y';") + diff("b.md", "+hi")

    assert changes(text) == [Change("src/a.ts", ("import x from 'x';",)), Change("b.md", ("hi",))]


def test_js_and_python_imports_become_package_names():
    f = facts(
        [
            Change(
                "a.ts",
                (
                    "import fetch from 'node-fetch';",
                    "const x = require('@scope/pkg/sub');",
                    "import './local';",
                    "await import('lodash/merge');",
                ),
            ),
            Change("b.py", ("import requests.adapters", "from yaml import safe_load")),
        ]
    )

    assert f.packages == {"node-fetch", "@scope/pkg", "lodash", "requests", "yaml"}


def test_dependency_lines_count_only_in_manifests():
    f = facts(
        [
            Change(
                "plugins/x/package.json", ('    "node-fetch": "^2.7.0",', '  "name": "x",', '  "version": "1.0.0",')
            ),
            Change("requirements-dev.txt", ("pytest>=8", "# comment")),
            Change("notes.md", ('"moment": "^2.0.0"',)),
        ]
    )

    assert f.packages == {"node-fetch", "pytest"}


def test_named_imports_are_recorded_with_their_module():
    f = facts([Change("Badge.tsx", ("import React, { FC, useState as useS } from 'react';",))])

    assert {("react", "FC"), ("react", "useState"), ("react", "React")} <= f.imported


def test_removed_lines_are_not_facts():
    f = facts(changes(diff("client.ts", "-import fetch from 'node-fetch';", " const a = 1;")))

    assert f.packages == set()
    assert f.paths == {"client.ts"}
