Name: fmf
Version: 0.2
Release: 1%{?dist}

Summary: Flexible Metadata Format
License: GPLv2+
BuildArch: noarch

URL: https://github.com/psss/fmf
Source: https://github.com/psss/fmf/archive/%{version}/fmf-%{version}.tar.gz

# Depending on the distro, we set some defaults.
# Note that the bcond macros are named for the CLI option they create.
# "%%bcond_without" means "ENABLE by default and create a --without option"

# Fedora (py3 executable, py2 & py3 subpackage, auto build requires)
%if 0%{?fedora}
%bcond_without python2
%bcond_without python3
%bcond_without py2executable # TODO: py2 until code is made py3 compatible
%bcond_with oldreqs

# RHEL6 and RHEL7 (py2 executable, py2 subpackage, manual build requires)
%else
%if 0%{?rhel} <= 7
%bcond_without python2
%bcond_with python3
%bcond_without py2executable
%bcond_without oldreqs

# RHEL8+ (py3 executable, py3 subpackage, auto build requires)
%else
%bcond_with python2
%bcond_without python3
%bcond_with py2executable
%bcond_with oldreqs
%endif
%endif

# Main fmf package requires corresponding python module
%if %{with py2executable}
Requires: python2-%{name}
%else
Requires: python%{python3_pkgversion}-%{name}
%endif

%description
The fmf Python module and command line tool implement a flexible
format for defining metadata in plain text files which can be
stored close to the source code. Thanks to hierarchical structure
with support for inheritance and elasticity it provides an
efficient way to organize data into well-sized text documents.
This package contains the command line tool.

%?python_enable_dependency_generator


# Python 2
%if %{with python2}
%package -n     python2-%{name}
Summary:        %{summary}
BuildRequires: python2-devel
BuildRequires: python2-setuptools
%if %{with oldreqs}
BuildRequires: pytest
BuildRequires: PyYAML
%else
BuildRequires: python2dist(pytest)
BuildRequires: python2dist(pyyaml)
%endif
%{?python_provide:%python_provide python2-%{name}}
%if %{with oldreqs}
Requires:       PyYAML
%endif

%description -n python2-%{name}
The fmf Python module and command line tool implement a flexible
format for defining metadata in plain text files which can be
stored close to the source code. Thanks to hierarchical structure
with support for inheritance and elasticity it provides an
efficient way to organize data into well-sized text documents.
This package contains the Python 2 module.
%endif


# Python 3
%if %{with python3}
%package -n     python%{python3_pkgversion}-%{name}
Summary:        %{summary}
BuildRequires: python%{python3_pkgversion}-devel
BuildRequires: python%{python3_pkgversion}-setuptools
BuildRequires: python%{python3_pkgversion}-pytest
BuildRequires: python%{python3_pkgversion}-PyYAML
%{?python_provide:%python_provide python%{python3_pkgversion}-%{name}}
%if %{with oldreqs}
Requires:       python%{python3_pkgversion}-PyYAML
%endif

%description -n python%{python3_pkgversion}-%{name}
The fmf Python module and command line tool implement a flexible
format for defining metadata in plain text files which can be
stored close to the source code. Thanks to hierarchical structure
with support for inheritance and elasticity it provides an
efficient way to organize data into well-sized text documents.
This package contains the Python 3 module.
%endif


%prep
%setup -q


%build
export LANG=en_US.utf-8 # for Python <= 3.6 and EPEL <= 7, but harmless

%if %{with python2}
%py2_build
%endif
%if %{with python3}
%py3_build
%endif


%install
export LANG=en_US.utf-8

%if %{with python2}
%py2_install
%endif

%if %{with python3}
%py3_install
%endif

%if %{with py2executable} && %{with python3}
rm -f %{buildroot}%{_bindir}/*
%py2_install
%endif

mkdir -p %{buildroot}%{_mandir}/man1
install -pm 644 fmf.1* %{buildroot}%{_mandir}/man1


%check
export LANG=en_US.utf-8

%if %{with python2}
%{__python2} -m pytest -vv
%endif

%if %{with python3}
%{__python3} -m pytest -vv || : # TODO the test fail here!
%endif


%{!?_licensedir:%global license %%doc}


%files
%{_mandir}/man1/*
%{_bindir}/%{name}
%license LICENSE

%if %{with python2}
%files -n python2-%{name}
%{python2_sitelib}/%{name}/
%{python2_sitelib}/%{name}-*.egg-info
%doc README.rst examples
%license LICENSE
%endif

%if %{with python3}
%files -n python%{python3_pkgversion}-%{name}
%{python3_sitelib}/%{name}/
%{python3_sitelib}/%{name}-*.egg-info
%doc README.rst examples
%license LICENSE
%endif


%changelog
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
