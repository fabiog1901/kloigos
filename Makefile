# Convenience commands for local development and documentation maintenance.
#
# Usage:
#   make help          Show available targets.
#   make format        Format Python code with isort and black.
#   make docs-write    Regenerate deterministic docs from source.
#   make docs-check    Verify generated docs and build the MkDocs site.
#   make docs-serve    Serve the MkDocs site locally.

.PHONY: help run format pre-commit docs-write docs-check docs-build docs-serve docs-clean py-compile

MKDOCS_SITE_DIR ?= /private/tmp/kloigos-mkdocs-site

help: ## Show this help message.
	@awk 'BEGIN {FS = ":.*##"; printf "Available targets:\n"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "  %-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

run: ## Run in development mode.
	poetry run fastapi run --reload kloigos/main.py

format: ## Format Python code with isort and black.
	poetry run isort .
	poetry run black .

pre-commit: format docs-check py-compile ## Run formatting and local checks before committing.

docs-write: ## Regenerate deterministic docs.
	poetry run python tools/generate_codemap.py

docs-check: ## Check generated docs are current and verify the MkDocs build.
	poetry run python tools/generate_codemap.py --check
	poetry run mkdocs build --strict --site-dir $(MKDOCS_SITE_DIR)

docs-build: docs-write ## Regenerate docs and build the MkDocs site into MKDOCS_SITE_DIR.
	poetry run mkdocs build --site-dir $(MKDOCS_SITE_DIR)

docs-serve: docs-write ## Regenerate docs and serve MkDocs locally.
	poetry run mkdocs serve -a localhost:8002

docs-clean: ## Remove the temporary MkDocs build output.
	rm -rf $(MKDOCS_SITE_DIR)

py-compile: ## Compile all Python files to catch syntax errors.
	poetry run python -m py_compile $$(find kloigos tools -type f -name '*.py' -not -path '*/__pycache__/*')
