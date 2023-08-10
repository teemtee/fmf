# Prepare variables
TMP = $(CURDIR)/tmp
VERSION = $(hatch version)
PACKAGE = fmf-$(VERSION)
FILES = LICENSE README.rst \
		Makefile fmf.spec pyproject.toml \
		examples fmf tests

# Define special targets
all: docs packages
.PHONY: docs hooks

# Temporary directory, include .fmf to prevent exploring tests there
tmp:
	mkdir -p $(TMP)/.fmf


# Run the test suite, optionally with coverage
test: tmp
	pytest tests/unit
smoke: tmp
	pytest tests/unit/test_smoke.py
coverage: tmp
	coverage run --source=fmf -m py.test tests
	coverage report
	coverage annotate


# Build documentation, prepare man page
docs: man
	cd docs && make html
man: source
	cp docs/header.txt $(TMP)/man.rst
	tail -n+7 README.rst >> $(TMP)/man.rst
	rst2man $(TMP)/man.rst > $(TMP)/$(PACKAGE)/fmf.1


# RPM packaging
source: clean tmp
	mkdir -p $(TMP)/SOURCES
	mkdir -p $(TMP)/$(PACKAGE)
	cp -a $(FILES) $(TMP)/$(PACKAGE)
tarball: source man
	cd $(TMP) && tar cfz SOURCES/$(PACKAGE).tar.gz $(PACKAGE)
	@echo ./tmp/SOURCES/$(PACKAGE).tar.gz
rpm: tarball
	rpmbuild --define '_topdir $(TMP)' -bb fmf.spec
srpm: tarball
	rpmbuild --define '_topdir $(TMP)' -bs fmf.spec
packages: rpm srpm


# Python packaging
wheel:
	python3 -m build
upload:
	twine upload dist/*.whl


# Vim tags and cleanup
tags:
	find fmf -name '*.py' | xargs ctags --python-kinds=-i
clean:
	rm -rf $(TMP) build dist .cache .pytest_cache fmf*.tar.gz
	find . -type f -name "*.py[co]" -delete
	find . -type f -name "*,cover" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf docs/_build
	rm -f .coverage tags
