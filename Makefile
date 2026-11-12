# One command per task. CI calls these same targets, so local and CI can't drift (ADR0008).
.DEFAULT_GOAL := help
.PHONY: help install format lint typecheck test-fast test test-integration eval audit check

UV   := uv run --locked
# All generated files live in .cache/ (git-ignored) so the project root stays clean.
export PYTHONPYCACHEPREFIX := $(CURDIR)/.cache/pycache
# Modules held to 100% branch coverage (ADR0008). Add each core module here as it is written.
CORE := */precedent/core/*,*/precedent/connectors/*
LICENCE_DENY := GPL;AGPL;SSPL;Commons Clause;Elastic License;Business Source

help:  ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-18s %s\n", $$1, $$2}'

install:  ## Install locked dependencies and git hooks
	uv sync --locked
	uvx pre-commit@4.6.2 install

format:  ## Auto-format and apply safe lint fixes
	$(UV) ruff format .
	$(UV) ruff check --fix .

lint:  ## Lint, format check, spelling, dependency hygiene, architecture contracts
	$(UV) ruff check .
	$(UV) ruff format --check .
	$(UV) codespell
	$(UV) deptry src
	$(UV) lint-imports --cache-dir .cache/import-linter

typecheck:  ## Static type check
	$(UV) ty check src tests evals

test-fast:  ## Unit tests only, no coverage (the edit-run loop)
	$(UV) pytest tests/unit -q

test:  ## All tests in parallel + coverage gates (>=90% overall, 100% core)
	$(UV) pytest -n auto --maxprocesses 4 --cov --cov-report=
	$(UV) coverage report --fail-under=90
	$(UV) coverage report --include='$(CORE)' --fail-under=100

test-integration:  ## Only tests that need FalkorDB (docker compose up -d)
	$(UV) pytest -m integration -q

eval:  ## Golden eval suites; pending until features land (release gate: EVAL_FLAGS=--strict)
	$(UV) python evals/run.py $(EVAL_FLAGS)

audit:  ## Vulnerabilities in all locked deps (dev tools run in CI too); licence gate on what we ship
	mkdir -p .cache
	uv export --frozen --format requirements-txt --no-emit-project --quiet -o .cache/requirements.txt
	uvx pip-audit@2.10.1 -r .cache/requirements.txt --disable-pip --progress-spinner off
	uv export --frozen --no-dev --format requirements-txt --no-emit-project --no-hashes --quiet -o .cache/requirements-runtime.txt
	uvx --with-requirements .cache/requirements-runtime.txt pip-licenses@5.5.5 --from=mixed --partial-match \
		--ignore-packages pip-licenses prettytable wcwidth tomli --fail-on="$(LICENCE_DENY)"

check: lint typecheck test audit  ## Everything CI runs, before you push
