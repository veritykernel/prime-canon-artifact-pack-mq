PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

.PHONY: deps validate tree

deps:
	$(PIP) install --upgrade pyyaml jsonschema

validate:
	$(PYTHON) scripts/validate_pack.py .

tree:
	find . -maxdepth 4 -type f | sort
