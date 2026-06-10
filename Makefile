# Convenience commands for local development and documentation maintenance.

.PHONY: help run serve migrate format pre-commit docs-write docs-check docs-build docs-serve docs-clean py-compile

MKDOCS_SITE_DIR ?= /private/tmp/kloigos-mkdocs-site

help: ## Show this help message.
	@awk 'BEGIN {FS = ":.*##"; printf "Available targets:\n"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "  %-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

run: serve ## Run in development mode.

serve: ## Serve the app through the application CLI.
	poetry run kloigos serve --reload

migrate: ## Apply cpkit and Kloigos database migrations.
	poetry run kloigos migrate

format: ## Format Python code with isort and black.
	poetry run isort .
	poetry run black .

codemap-write: ## Refresh deterministic CODEMAP.md and .build/project-index.json.
	poetry run python tools/codemap.py --write

codemap-check: ## Verify deterministic codemap outputs are current.
	poetry run python tools/codemap.py --check

pre-commit: format codemap-write py-compile ## Run required pre-commit maintenance.

docs-check: ## Check generated docs are current and verify the MkDocs build.
	poetry run mkdocs build --strict --site-dir $(MKDOCS_SITE_DIR)

docs-build: codemap-write ## Regenerate docs and build the MkDocs site into MKDOCS_SITE_DIR.
	poetry run mkdocs build --site-dir $(MKDOCS_SITE_DIR)

docs-serve: codemap-write ## Regenerate docs and serve MkDocs locally.
	poetry run mkdocs serve -a localhost:8002

docs-clean: ## Remove the temporary MkDocs build output.
	rm -rf $(MKDOCS_SITE_DIR)

py-compile: ## Compile all Python files to catch syntax errors.
	poetry run python -m py_compile $$(find kloigos tools -type f -name '*.py' -not -path '*/__pycache__/*')
