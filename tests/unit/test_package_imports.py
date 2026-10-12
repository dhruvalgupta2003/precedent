import importlib
import pkgutil

import pytest

import precedent

MODULES = sorted(m.name for m in pkgutil.walk_packages(precedent.__path__, prefix="precedent."))


@pytest.mark.parametrize("module", MODULES)
def test_every_module_imports_cleanly(module):
    """Catches syntax errors, missing dependencies and import cycles before anything runs them."""
    importlib.import_module(module)
