Name:          fmf
Version:       0.0.0
Release:       1%{?dist}

Summary:       Flexible Metadata Format
License:       GPL-2.0-or-later
BuildArch:     noarch

URL:           https://github.com/teemtee/fmf
Source:        %{pypi_source fmf}

# Main fmf package requires the Python module
BuildRequires: python3-devel
BuildRequires: python3dist(docutils)
BuildRequires: git-core
Requires:      git-core

Obsoletes:     python3-fmf < %{version}-%{release}
%py_provides   python3-fmf

%description
The fmf Python module and command line tool implement a flexible
format for defining metadata in plain text files which can be
stored close to the source code. Thanks to hierarchical structure
with support for inheritance and elasticity it provides an
efficient way to organize data into well-sized text documents.


%prep
%autosetup -p1 -n fmf-%{version}


%generate_buildrequires
%pyproject_buildrequires -x tests %{?epel:-w}


%build
%pyproject_wheel
cp docs/header.txt man.rst
tail -n+7 README.rst >> man.rst
rst2man man.rst > fmf.1


%install
%pyproject_install
%pyproject_save_files fmf

mkdir -p %{buildroot}%{_mandir}/man1
install -pm 644 fmf.1* %{buildroot}%{_mandir}/man1


%check
%pyproject_check_import


%files -f %{pyproject_files}
%{_mandir}/man1/*
%{_bindir}/%{name}
%doc README.rst examples


%changelog
* Mon Jun 17 2024 Lukáš Zachar <lzachar@redhat.com> - 1.4.1-1
- Use local dict instead of modifying `locals()`

* Wed Jun 05 2024 Petr Šplíchal <psplicha@redhat.com> - 1.4.0-1
- Introduce a new page for release notes
- Extend the `filter()` documentation slightly
- Implement the '~' merge operation
- Support escaping `|` and `&` in `utils.filter()`
- Accept additional rules in the `adjust()` call (#230)
- Avoid `copy()` calls in `adjust()`
- Directive `select` to control node selection
- Allow filtering based on the node name
- Drop epel-8
- Fix github action
- Remove travis.yaml
- Turn schema validation method into a stand-alone function
- Limit number of tests run for integration with tmt (#225)
- Add a `Toolbelt Catalog` entry for `fmf`

* Fri Sep 29 2023 Petr Šplíchal <psplicha@redhat.com> - 1.3.0-1
- Allow case-insensitive context matching
- Move the copr repository to the `teemtee` group
- Fix missing file require for unit tests
- Add callback to adjust() to make it observable by callers
- Drop support for `el-8` and `python-3.6`
- Fix docs building on readthedocs
- Install `yq` needed for `tmt` integration tests
- Include `srpm_build_deps` in the packit config
- Remove `metadata` from Packit config
- Add missing build job to Packit config
- Update pre-commit checks to the latest versions
- Require `fmf` in tests, remove obsolete coverage
- Fix a typo in the merging minus sign documentation

* Thu Jul 21 2022 Lukáš Zachar <lzachar@redhat.com> - 1.2.1-1
- Retry if shallow clone fails

* Tue Jul 19 2022 Lukáš Zachar <lzachar@redhat.com> - 1.2.0-1
- Shallow git clone if no reference is used
- Select by the source of object
- Enable the flake8 check, fix detected issues
- Make when in adjust optional, add true|false expr.
- Version as fmf flag and module attribute

* Wed Jun 08 2022 Lukáš Zachar <lzachar@redhat.com> - 1.1.0-1
- Implement a directive for disabling inheritance
- Add support for prepending items during merging
- Explicitly convert context value to string
- Workaround s390x ruamel read issue
- Support reference schemas in validation function
- Add JSON Schema validation method
- Fixes blocking with symbolic link loops
- Use a better way to detect the default git branch
- Add unit tests for comma operator in context rules
- Add examples demonstrating the context syntax

* Thu Nov 11 2021 Petr Šplíchal <psplicha@redhat.com> - 1.0.0-1
- Migrate yaml parsing to ruamel.yaml
- Drop support for Python 2
- Add extra requires and enable readthedocs config (#143)
- Filter accept value with a colon
- Adjust style to fix issues revealed by pre-commit
- Enable pre-commit, update contribution docs
- Disable integration testing with tmt for centos-7

* Thu Apr 15 2021 Petr Šplíchal <psplicha@redhat.com> - 0.16.0-1
- Add support for empty files and virtual nodes
- Change outcome of CannotDecide operations
- Enable copr builds from master for epel-7 as well
- Define dict method to get child or data item
- Keep original adjust rules when adjusting nodes
- Use a deep copy when storing raw node data
- Fix warnings in pytest

* Fri Mar 26 2021 Petr Šplíchal <psplicha@redhat.com> - 0.15.2-1
- Do not use mutable objects as default arguments
- A bunch of adjustments for the epel-7 build

* Wed Mar 24 2021 Petr Šplíchal <psplicha@redhat.com> - 0.15-1
- Implement the new 'fmf clean' command
- Functions to manipulate cache
- Fetch the whole tree using utils.fetch_tree()
- Raise FileException on duplicate YAML keys
- Allow to set desired cache location
- Adjust support for storing modified data to disk
- Add support for storing modified metadata to disk
- Prevent exploring tests in the tmt directory
- Simplify special distro comparison examples
- Store command output in run(), fetch() exceptions
- Use filelock for locking, expand test coverage
- Adjust locking for Tree.node() and utils.fetch()
- Use locking to checkout/read tree
- Enable integration testing with tmt, some cleanup
- Implement a new method copy() for cloning nodes
- Adjust fetch() with custom destination and env
- Support calls fetch(destination, env) and run(env)
- Use the origin default branch instead of master
- Store commit hash if the tree is under a git repo

* Tue Jan 12 2021 Petr Šplíchal <psplicha@redhat.com> - 0.14-1
- Adjust context docs, fix typos, style cleanup
- Left vs Right side in Context matches
- Simplify deep merging, adjust test suite a bit
- Implement recursive merging of data
- Remove the duplicate build job from packit config
- Adjust 'make test' to work under virtualenv
- Update the adjust continue key default to True

* Wed Nov 18 2020 Petr Šplíchal <psplicha@redhat.com> - 0.13-1
- Enable copr builds from master, simplify config
- Adjust documentation for the new Context class
- Add documentation for the new Context class
- Add a new Tree.adjust() method for handling rules
- Context: Better operator names, comments
- Adjust the new Context implementation
- Context implementation

* Thu Jun 04 2020 Petr Šplíchal <psplicha@redhat.com> - 0.12-1
- Do git pull in utils.fetch
- Make fetch._run official as utils.run

* Tue Mar 17 2020 Petr Šplíchal <psplicha@redhat.com> - 0.11-2
- Enable back python2-fmf subpackage for RHEL7

* Fri Feb 14 2020 Petr Šplíchal <psplicha@redhat.com> - 0.11-1
- Add git to BuildRequires (now required by tests)
- Use coveralls to report coverage results
- Adjust Tree.node() implementation, extend tests
- Get metadata for unique id [fix #67]
- Use the fedora-all target in packit config (#72)
- Define the full fmf identifier [fix #52]
- A minor cleanup of the concept documentation
- Always ignore special system directories
- Filesystem root and inaccessible dirs [fix #70]
- Rename the 'testsets' directory to 'plans'

* Wed Oct 30 2019 Petr Šplíchal <psplicha@redhat.com> - 0.10-1
- Mock is not needed for docs, fix missing new line
- Provide a public static method Tree.init()

* Wed Oct 09 2019 Petr Šplíchal <psplicha@redhat.com> - 0.9-1
- Support custom conjunction like 'or' in listed()
- Update smoke testset to the latest L2 spec
- Fix build conditional default for englocale
- Use raw strings for regular expression patterns

* Mon Sep 30 2019 Petr Šplíchal <psplicha@redhat.com> - 0.8-1
- Update spec to build Python 3 packages only
- Move unit tests into a separate directory
- Move testsets, include a super simple smoke test
- Initial set of stories and tests
- Enable beakerlib smoke test in the testing farm
- Add a simple beakerlib test for command line help
- Clean up the docs build folder directly
- Enable packit

* Fri Jul 26 2019 Petr Šplíchal <psplicha@redhat.com> - 0.7-1
- Support both old and new yaml loader
- Add advanced python filtering [fix #55]
- Drop explicit locale setting during build and install
- Drop Python 2 subpackage on Fedora 30+ (#1647798)
- Better handle yaml errors [fix #50]
- Support reducing attributes using the "-" suffix
- Prevent extra new lines in the show() output
- Adjust FullLoader to load all strings as unicode
- Suppress yaml warnings by specifying the loader
- Support Tree.find() for non-leaf nodes as well

* Mon Oct 08 2018 Petr Šplíchal <psplicha@redhat.com> 0.6-1
- Ignore directories with no metadata defined
- Give a nice error when .fmf file exists [fix #37]
- Ignore metadata subtrees [fix #43]
- Support for direct deep dictionary value retrieval
- Separate exception for missing tree root [fix #42]
- Move data merging into a separate method [fix #41]
- Ensure that data or parent are provided for Tree
- Test coverage for yaml syntax and finding root
- Do not walk through the whole directory hierarchy
- Example typo, handle yaml parse errors [fix #38]
- Require the same version of the rpm package

* Tue Jun 12 2018 Petr Šplíchal <psplicha@redhat.com> 0.5-1
- Add support for subcommands [fix #32]
- Define metadata tree root [fix #26]
- Enable regular expressions in --filter [fix #35]
- Support merging dictionary values as well
- Build Python 3 package for pip as well
- Add more detailed logging for easier debugging
- Correctly handle deep inheritance [fix #31]
- Load all strings from YAML files as Unicode
- Prevent data modification in filter [fix #30]
- Fix inheritance of scattered files [fix #25]

* Wed May 09 2018 Petr Šplíchal <psplicha@redhat.com> 0.4-1
- Do not gzip the man page, fix the source link [BZ#1575645]

* Wed Apr 25 2018 Petr Šplíchal <psplicha@redhat.com> 0.3-1
- Remove the unreliable syntactic sugar [fix #2]
- Add a simple example of a BeakerLib test
- Improve the output, fix the encoding issue [#21]
- Add sources as value for string formatting
- Show source files in debug mode [fix #15]
- Allow deeper one-line hierarchy [fix #17]
- Update the list of supported Python versions
- Use name 'root' for directory where Tree is rooted
- Fix the full path custom format example
- Move documentation to the fmf rpm package
- Remove entry_points, custom format merged into fmf
- Add a few custom format examples
- Update docs with the custom format support
- Run both Python 2 and Python 3 tests locally
- Make eval() work with with Python 3 as well
- Integrate custom formatting into base & cli
- The first draft of output formatting
- Enable python3 tests, python3 executable in Fedora
- Python 3 compatibility changes
- Show nothing if there are no metadata [fix #12]
- Clean up before preparing the source files
- Make setup methods compatible with older pytest

* Mon Apr 09 2018 Petr Šplíchal <psplicha@redhat.com> 0.2-1
- Build a separate fmf package for the executable
- Add docs example for setting up storage
- Improve command line test coverage
- Smoke tests for logging and coloring
- Tests for pluralize, listed and split
- Include a simple example of python code
- Separate base tests, forgotten asserts, cleanup
- Several adjustments for the attributes adding
- Adding ability to add value to parent attribute
- Fix Tree.get() to correctly return data
- Make the spec do python2 & python3 and EPEL & Fedora
- Ignore hidden files and directories when searching
- Add test coverage for the filter function
- Extend the list of examples, fix hierarchy typos
- Enable Travis Continuous Integration

* Mon Jan 22 2018 Petr Šplíchal <psplicha@redhat.com> 0.1-1
- Initial packaging.
