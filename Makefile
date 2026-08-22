.DEFAULT_GOAL := help
MAKEFLAGS += --no-print-directory

PY     ?= uv run python
KERNEL ?= template-app

# Recipes are prefixed with @ so make does not echo the command itself — the
# scripts print their own progress, which is the part worth reading.

.PHONY: help setup app pipeline ingestion transform notebooks notebook-kernel report doctor ci clean

help:  ## Show this list
	@awk 'BEGIN {FS = ":.*?## "} /^[a-z-]+:.*?## / {printf "  make %-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup:  ## Install dependencies and the notebook kernel
	@uv sync
	@$(MAKE) notebook-kernel

app:  ## Run the Streamlit app
	@uv run streamlit run app.py

# ── The pipeline ──────────────────────────────────────────────────────────────
# One command for the whole ETL. Each stage also runs on its own, and `ingestion`
# is a no-op until you add a source module to 01_ingestion/.

pipeline:  ## Run the whole ETL: ingestion -> tables -> notebooks
	@$(MAKE) ingestion
	@$(MAKE) transform
	@$(MAKE) notebooks

ingestion:  ## Fetch raw data into 02_data/raw/ (this stage only)
	@$(PY) 01_ingestion/run.py

transform:  ## Build 02_data/tables/ from 02_data/raw/
	@$(PY) -m backend.transform

# Runs each notebook for its side effects — the storage.save() calls — and
# discards the rendered copy, so executing never dirties the .ipynb files.
notebooks:  ## Execute every notebook in 03_notebooks/
	@echo "[notebooks] executing 03_notebooks/*.ipynb"
	@$(PY) -m nbconvert --to notebook --execute --stdout --log-level=ERROR \
		--ExecutePreprocessor.kernel_name=$(KERNEL) \
		"--ExecutePreprocessor.extra_arguments=['--IPKernelApp.log_level=ERROR']" \
		03_notebooks/*.ipynb > /dev/null
	@echo "[notebooks] done"

# ── Everything else ───────────────────────────────────────────────────────────

notebook-kernel:  ## Install/refresh the project Jupyter kernel
	@$(PY) -m ipykernel install --user --name $(KERNEL) --display-name "Template App (.venv)"

doctor:  ## Check config and credentials, and say what is wrong
	@$(PY) -m backend.doctor

report:  ## Print what the pipeline currently is: sources, tables, pages
	@$(PY) -m backend.report

ci:  ## Compile everything and smoke-test the app
	@echo "[ci] compiling backend, ingestion, app and pages"
	@$(PY) -m compileall -q backend 01_ingestion app.py 04_pages
	@echo "[ci] rendering every page and checking the tables they read"
	@uv run pytest 05_tests -v -ra --tb=short --no-header

clean:  ## Remove __pycache__ directories and stray kernel sockets
	@$(PY) -c "import pathlib, shutil; [shutil.rmtree(p, True) for p in pathlib.Path('.').rglob('__pycache__')]"
	@rm -f 03_notebooks/kernel-ipc-*
