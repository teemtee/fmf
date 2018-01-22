# Prepare variables
TMP = $(CURDIR)/tmp
VERSION = $(shell grep ^Version fmf.spec | sed 's/.* //')
PACKAGE = fmf-$(VERSION)
FILES = LICENSE README.rst \
		Makefile fmf.spec \
		examples fmf bin

# Define special targets
all: docs packages
.PHONY: docs hooks

# Temporary directory
tmp:
	mkdir $(TMP)


# Run the test suite, optionally with coverage
test: tmp
	py.test tests
smoke: tmp
	py.test tests/test_smoke.py
coverage: tmp
	coverage run --source=fmf,bin -m py.test tests
	coverage report
	coverage annotate


# Build documentation, prepare man page
docs: man
	cd docs && make html
man: source
	cp docs/header.txt $(TMP)/man.rst
	tail -n+7 README.rst >> $(TMP)/man.rst
	rst2man $(TMP)/man.rst | gzip > $(TMP)/$(PACKAGE)/fmf.1.gz


# RPM packaging
source:
	mkdir -p $(TMP)/SOURCES
	mkdir -p $(TMP)/$(PACKAGE)
	cp -a $(FILES) $(TMP)/$(PACKAGE)
tarball: source man
	cd $(TMP) && tar cfj SOURCES/$(PACKAGE).tar.bz2 $(PACKAGE)
rpm: tarball
	rpmbuild --define '_topdir $(TMP)' -bb fmf.spec
srpm: tarball
	rpmbuild --define '_topdir $(TMP)' -bs fmf.spec
packages: rpm srpm


# Python packaging
wheel:
	python setup.py bdist_wheel
upload:
	twine upload dist/*.whl


# Git hooks, vim tags and cleanup
hooks:
	ln -snf ../../hooks/pre-commit .git/hooks
	ln -snf ../../hooks/commit-msg .git/hooks
tags:
	find fmf -name '*.py' | xargs ctags --python-kinds=-i
clean:
	rm -rf $(TMP) build dist fmf.egg-info
	find . -type f -name "*.py[co]" -delete
	find . -type f -name "*,cover" -delete
	find . -type d -name "__pycache__" -delete
	cd docs && make clean
	rm -f .coverage tags
