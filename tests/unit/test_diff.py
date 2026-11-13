import time

import pytest

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


MOMENT_FILE = ("import moment from 'moment';", "", "export const shown = moment(day).format('L');")
NEW_USES = [
    ("a new call", MOMENT_FILE, ("const due = moment(day).add(3, 'days');",), (), {"moment"}),
    ("an edited call", MOMENT_FILE, ("export const shown = moment(day).format('LL');",), MOMENT_FILE[2:], set()),
    (
        "a renamed named import",
        ("import { duration as d } from 'moment';",),
        ("const t = d(5, 'minutes');",),
        (),
        {"moment"},
    ),
    ("a namespace import", ("import * as m from 'moment';",), ("m.utc();",), (), {"moment"}),
    ("a require", ("const moment = require('moment');",), ("moment();",), (), {"moment"}),
    ("a python module", ("import requests",), ("requests.get(url)",), (), {"requests"}),
    ("a python alias", ("import numpy as np",), ("np.zeros(3)",), (), {"numpy"}),
    ("a python name", ("from requests import get as fetch",), ("fetch(url)",), (), {"requests"}),
    ("only in a string or comment", MOMENT_FILE, ("log('moment is slow'); // moment",), (), set()),
    ("a property of something else", MOMENT_FILE, ("clock.moment();",), (), set()),
    ("a relative import", ("import util from './util';",), ("util();",), (), set()),
    ("a file with no imports", (), ("moment();",), (), set()),
]


@pytest.mark.parametrize(
    ("context", "added", "removed", "used"), [c[1:] for c in NEW_USES], ids=[c[0] for c in NEW_USES]
)
def test_new_uses_of_a_name_the_file_already_imports_are_found(context, added, removed, used):
    assert facts([Change("src/a.ts", added, removed, context)]).used == used


def test_a_package_imported_in_the_same_change_is_an_import_not_a_new_use():
    f = facts([Change("src/a.ts", ("import moment from 'moment';", "moment();"), (), MOMENT_FILE)])

    assert (f.packages, f.used) == ({"moment"}, set())


def test_a_new_use_in_a_docs_file_is_not_code():
    assert facts([Change("README.md", ("moment();",), (), MOMENT_FILE)]).used == set()


@pytest.mark.parametrize(
    "line",
    ["import " + "{" * 50_000 + " from 'a'", "import a" + " " * 50_000 + "x", "const x = 1;" + " " * 50_000],
    ids=["many braces", "many spaces", "long code line"],
)
def test_a_crafted_long_line_is_read_quickly(line):
    started = time.monotonic()
    facts([Change("src/a.ts", (line,), (), (line, *MOMENT_FILE))])

    assert time.monotonic() - started < 0.5


def test_a_file_with_thousands_of_imports_is_read_quickly():
    imports = tuple(f"import n{i} from 'p{i}';" for i in range(20_000))
    started = time.monotonic()
    found = facts([Change("src/a.ts", tuple(f"n{i}();" for i in range(20_000)), (), imports)])

    assert time.monotonic() - started < 2
    assert len(found.used) == 20_000
