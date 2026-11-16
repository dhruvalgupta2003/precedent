"""Places and homes (docs/design/production-architecture.md \u00a74.1, phase 1a).

A file's home comes from the folder it sits in, never from a field, so nobody can widen a check's reach by editing
it. One reach has exactly one home value, however the file was found. `places.yaml` (central repo) maps places to
repos and folders, with one owner team each; a place's parent follows from its repo and folder, so there's no cycle.
Whether an owner team has at least two active members is checked against GitHub by `precedent/policy` (phase 3).
"""

import pytest

from precedent.connectors.checks_file import read_places
from precedent.core.checks import Home
from precedent.core.errors import KnowledgeError
from precedent.core.places import Places, home_of

PLACES = """\
places:
  shop: {repo: shop, owner: "@acme/shop"}
  payments: {repo: shop, path: services/payments, owner: "@acme/payments", tags: [services]}
  orders: {repo: shop, path: services/orders, owner: "@acme/orders", tags: [services, browser-packages]}
  web: {repo: web, owner: "@acme/web", tags: [browser-packages]}
"""


def places(text: str = PLACES) -> Places:
    return read_places(text.encode(), "places.yaml")


def test_places_read_with_their_repo_folder_owner_and_tags():
    payments = places().get("payments")

    assert payments is not None
    assert payments.model_dump() == {
        "name": "payments",
        "repo": "shop",
        "path": "services/payments",
        "owner": "@acme/payments",
        "tags": ("services",),
    }


def test_a_place_parent_follows_from_repo_and_folder():
    loaded = places()
    parent = loaded.parent("payments")

    assert parent is not None
    assert parent.name == "shop"
    assert loaded.parent("shop") is None  # only the org is above a whole repo
    assert loaded.parent("web") is None


PLACES_REFUSED = {
    "no owner": ("places:\n  shop: {repo: shop}\n", "owner"),
    "no repo": ('places:\n  shop: {owner: "@acme/shop"}\n', "repo"),
    "unknown field": ('places:\n  shop: {repo: shop, owner: "@a/b", ownr: x}\n', "unknown field ownr"),
    "owner not a handle": ("places:\n  shop: {repo: shop, owner: shop team}\n", ": owner: "),
    "owner a single person": ('places:\n  shop: {repo: shop, owner: "@alice"}\n', ": owner: "),
    "dot-only team": ('places:\n  x: {repo: shop, owner: "@acme/.."}\n', ": owner: "),
    "path leaves the repo": ('places:\n  x: {repo: shop, path: ../y, owner: "@a/b"}\n', ": path: "),
    "wildcard in a folder": ('places:\n  x: {repo: shop, path: "services/*", owner: "@a/b"}\n', ": path: "),
    "path not text": ('places:\n  shop: {repo: shop, path: 5, owner: "@a/b"}\n', ": path: "),
    "repo not a name": ('places:\n  x: {repo: "../evil", owner: "@a/b"}\n', ": repo: "),
    "repo is a dot": ('places:\n  x: {repo: "..", owner: "@a/b"}\n', ": repo: "),
    "tag not a name": ('places:\n  x: {repo: shop, owner: "@a/b", tags: ["Not A Tag"]}\n', ": tags: "),
    "two places on one folder": (
        'places:\n  a: {repo: shop, path: s/x, owner: "@a/b"}\n  b: {repo: shop, path: s/x/, owner: "@a/c"}\n',
        "folder shop:s/x appears twice",
    ),
    "reserved name org": ('places:\n  org: {repo: shop, owner: "@a/b"}\n', "reserved"),
    "bad place name": ('places:\n  Pay Ments: {repo: shop, owner: "@a/b"}\n', ": name: "),
    "place not a mapping": ("places:\n  shop: just-text\n", "shop: expected repo"),
    "no places": ("places: {}\n", "at least one place"),
    "not a mapping": ("- a\n", "at least one place"),
}


@pytest.mark.parametrize(("text", "named"), PLACES_REFUSED.values(), ids=PLACES_REFUSED.keys())
def test_every_places_mistake_stops_the_load(text, named):
    with pytest.raises(KnowledgeError) as refused:
        places(text)

    assert named in str(refused.value)


HOMES = {
    "a code repo's root precedent folder": ("shop", "precedent/checks.yaml", Home(repo="shop")),
    "a mapped service folder": (
        "shop",
        "services/payments/precedent/checks.yaml",
        Home(repo="shop", path="services/payments"),
    ),
    "the central repo's org folder": ("decisions", "homes/org/checks.yaml", Home()),
    "the central repo's place folder": (
        "decisions",
        "homes/payments/promotions.yaml",
        Home(repo="shop", path="services/payments"),
    ),
    "a repo-level place in the central repo": ("decisions", "homes/web/checks.yaml", Home(repo="web")),
}


@pytest.mark.parametrize(("repo", "file", "home"), HOMES.values(), ids=HOMES.keys())
def test_a_files_home_comes_from_its_folder(repo, file, home):
    assert home_of(repo, file, places(), central="decisions") == home


def test_one_reach_has_one_home_however_its_file_is_found():
    """A service's own folder and its folder in the central repo are the same home; so are a repo and its place."""
    loaded = places()

    assert home_of("shop", "services/payments/precedent/checks.yaml", loaded, "decisions") == home_of(
        "decisions", "homes/payments/checks.yaml", loaded, "decisions"
    )
    assert home_of("web", "precedent/checks.yaml", loaded, "decisions") == home_of(
        "decisions", "homes/web/checks.yaml", loaded, "decisions"
    )


HOME_REFUSED = {
    "an unmapped service folder": ("shop", "services/billing/precedent/checks.yaml", "services/billing"),
    "a folder not named precedent": ("shop", "config/checks.yaml", "precedent"),
    "an unknown place in the central repo": ("decisions", "homes/billing/checks.yaml", "billing"),
    "a file deeper in a home folder": ("decisions", "homes/payments/x/checks.yaml", "homes/payments"),
}


@pytest.mark.parametrize(("repo", "file", "named"), HOME_REFUSED.values(), ids=HOME_REFUSED.keys())
def test_a_file_without_a_known_home_is_refused(repo, file, named):
    with pytest.raises(KnowledgeError, match=named):
        home_of(repo, file, places(), central="decisions")


def test_without_places_a_root_precedent_folder_is_its_repo():
    """Local mode: one repository and no central repo."""
    assert home_of("shop", "precedent/checks.yaml", Places(), central=None) == Home(repo="shop")


TAGS = {
    "org home sees every tagged place": (Home(), "browser-packages", {("shop", "services/orders"), ("web", "")}),
    "repo home sees its own tagged places": (
        Home(repo="shop"),
        "services",
        {("shop", "services/payments"), ("shop", "services/orders")},
    ),
    "place home sees tagged places inside it": (
        Home(repo="shop", path="services/payments"),
        "services",
        {("shop", "services/payments")},
    ),
}


@pytest.mark.parametrize(("home", "tag", "found"), TAGS.values(), ids=TAGS.keys())
def test_a_tag_only_reaches_places_inside_the_home(home, tag, found):
    assert places().tagged(tag, within=home) == found


def test_an_unknown_tag_is_refused():
    with pytest.raises(KnowledgeError, match="no place has the tag"):
        places().tagged("no-such-tag", within=Home())


def test_a_tag_with_no_place_inside_the_home_is_refused():
    """A check whose tag matches nothing in its home could never match: it must not load as if it would."""
    with pytest.raises(KnowledgeError, match="inside this home"):
        places().tagged("browser-packages", within=Home(repo="shop", path="services/payments"))
