.PHONY: check lint fix deptry install

# Default task: run all checks
check: lint deptry

lint:
	uv run ruff check .
	uv run ruff format --check .

fix:
	uv run ruff check --fix .
	uv run ruff format .

deptry:
	uv run deptry .

install:
	uv sync --group lint --editable
