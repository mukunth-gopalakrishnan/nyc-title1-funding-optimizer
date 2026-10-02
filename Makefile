.PHONY: help setup install dev verify demo test lint fmt run report sweep \
        wizard runs compare scenarios dashboard clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup:  ## create .venv, install everything, and verify it works
	./scripts/setup.sh

# Editable installs of a pyproject-only project need pip >= 21.3; macOS ships
# 3.9 with pip 21.2, where `pip install -e .` fails with a confusing message
# about a missing setup.py.
install:  ## install the package into the active environment
	python -m pip install --upgrade pip
	pip install -e .

dev:  ## install with dev and dashboard extras
	python -m pip install --upgrade pip
	pip install -e ".[dev,dashboard]"

verify:  ## check this installation works and reproduces the published results
	titlei verify

demo:  ## guided end-to-end walkthrough
	titlei demo

test:  ## run the test suite
	pytest

lint:  ## check style
	ruff check src tests dashboard

fmt:  ## autofix style
	ruff check --fix src tests dashboard

run:  ## run the model, write CSV outputs
	titlei run --out outputs -v

report:  ## build the static HTML report
	titlei report --out outputs -v

sweep:  ## budget sensitivity table
	titlei sweep

wizard:  ## build a scenario by answering a questionnaire
	titlei wizard

runs:  ## list saved runs
	titlei runs

compare:  ## overlay and rank every saved run
	titlei compare

scenarios:  ## register a standard set of scenarios, then compare them
	titlei run --label "Published 500M (control)" --control --replace
	titlei run --budget 250e6 --label "Half budget" --replace
	titlei run --budget 1e9   --label "Double budget" --replace
	titlei run --financial-weight 1.0 --label "Financial need only" --replace
	titlei run --low-need-cap 5000 --label "Equal caps" --replace
	titlei compare "Published 500M (control)" "Half budget" "Double budget" \
		"Financial need only" "Equal caps"

dashboard:  ## launch the interactive dashboard
	streamlit run dashboard/app.py

clean:
	rm -rf outputs/charts outputs/tables outputs/comparison outputs/report.html \
		.pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
