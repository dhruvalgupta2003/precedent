from precedent.core.diff import Change, changes, facts


def diff(path: str, *lines: str) -> str:
    return f"--- a/{path}\n+++ b/{path}\n@@ -1,1 +1,2 @@\n" + "\n".join(lines) + "\n"


def test_a_unified_diff_gives_each_file_with_its_added_and_removed_lines():
    text = diff("src/a.ts", "+import x from 'x';", " unchanged", "-import y from 'y';") + diff("b.md", "+hi")

    assert changes(text) == [
        Change("src/a.ts", ("import x from 'x';",), ("import y from 'y';",)),
        Change("b.md", ("hi",)),
    ]


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


def test_documentation_is_not_code_but_manifests_still_count():
    f = facts(
        [
            Change("docs/migrating.md", ("import fetch from 'node-fetch';", "export default app.createRoot();")),
            Change("README.mdx", ("import moment from 'moment';",)),
            Change("requirements.txt", ("requests>=2",)),
        ]
    )

    assert f.packages == {"requests"}
    assert "export default" not in f.text


def test_a_re_export_counts_as_using_the_package():
    f = facts(
        [Change("http.ts", ("export { default as fetch } from 'node-fetch';", "export * from '@scope/pkg/sub';"))]
    )

    assert f.packages == {"node-fetch", "@scope/pkg"}


def test_a_namespace_or_default_import_records_its_alias():
    f = facts([Change("Badge.tsx", ("import * as R from 'react';", "import Lodash from 'lodash';"))])

    assert f.aliases == {"R": "react", "Lodash": "lodash"}


def test_export_as_default_reads_as_export_default():
    f = facts([Change("Badge.tsx", ("export { Badge as default };",))])

    assert "export default Badge" in f.code


def test_strings_and_comments_are_not_code():
    f = facts([Change("a.ts", ("const label = 'export default'; // export default here", "export default x;"))])

    assert f.code.count("export default") == 1


def test_a_line_moved_within_the_change_is_not_new():
    moved = changes(
        "--- a/a.ts\n+++ b/a.ts\n@@ -1 +0,0 @@\n-import fetch from 'node-fetch';\n"
        "--- a/b.ts\n+++ b/b.ts\n@@ -0,0 +1 @@\n+import fetch from 'node-fetch';\n"
    )

    assert facts(moved).packages == set()
