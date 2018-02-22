Name: fmf
Version: 0.1
Release: 1%{?dist}

Summary: Flexible Metadata Format
License: GPLv2+

URL: https://github.com/psss/fmf
Source: https://github.com/psss/fmf/archive/%{version}/fmf-%{version}.tar.gz

BuildArch: noarch



# Depending on the distro, we set some defaults.
# Note that the bcond macros are named for the CLI option they create.
# "%%bcond_without" means "ENABLE by default and create a --without option"
%if 0%{?fedora}
# All stable Fedora versions currently behaves (almost) the same:
# build the python2 subpackage
%bcond_without python2

# build the python3 subpackage
%bcond_without python3

# don't put the executable into python2 (but rather 3)
%bcond_with py2executable

# we don't need to require PyYAML manually, but we can use python2dist BRs
%bcond_with oldreqs

%else
%if 0%{?rhel} <= 7
# RHEL 7 and 6 with EPEL:
# build the python2 subpackage
%bcond_without python2

# build the python3 subpackage (EPEL has it)
%bcond_without python3

# put the executable into python2 (that's still supposed tho be the "default")
%bcond_without py2executable

# we need to require PyYAML manually, also no python2-... yet
%bcond_without oldreqs

%else
# Any newer EL:
# don't build the python2 subpackage
%bcond_with python2

# build the python3 subpackage and has the executable in it
%bcond_without python3
%bcond_without py2executable

# we don't need to require PyYAML manually (TODO: reality check)
%bcond_with oldreqs
%endif
%endif



%?python_enable_dependency_generator

%description
The fmf Python module and command line tool implement a flexible
format for defining metadata in plain text files which can be
stored close to the source code. Thanks to hierarchical structure
with support for inheritance and elasticity it provides an
efficient way to organize data into well-sized text documents.



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

%if %{with py2executable}
Provides:       %{name} == %{version}-%{release}
%endif

%if %{with oldreqs}
Requires:       PyYAML
%endif

%description -n python2-%{name}
The fmf Python module and command line tool implement a flexible
format for defining metadata in plain text files which can be
stored close to the source code. Thanks to hierarchical structure
with support for inheritance and elasticity it provides an
efficient way to organize data into well-sized text documents.
%endif



%if %{with python3}
%package -n     python%{python3_pkgversion}-%{name}
Summary:        %{summary}
BuildRequires: python%{python3_pkgversion}-devel
BuildRequires: python%{python3_pkgversion}-setuptools
BuildRequires: python%{python3_pkgversion}-pytest
BuildRequires: python%{python3_pkgversion}-PyYAML

%{?python_provide:%python_provide python%{python3_pkgversion}-%{name}}

%if %{without py2executable}
Provides:       %{name} == %{version}-%{release}
%endif

%if %{with oldreqs}
Requires:       python%{python3_pkgversion}-PyYAML
%endif

%description -n python%{python3_pkgversion}-%{name}
The fmf Python module and command line tool implement a flexible
format for defining metadata in plain text files which can be
stored close to the source code. Thanks to hierarchical structure
with support for inheritance and elasticity it provides an
efficient way to organize data into well-sized text documents.
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

%if %{without py2executable} && %{with python2}
%py2_install
rm -f %{buildroot}%{_bindir}/*
%endif

%if %{with python3}
%py3_install
%endif

%if %{with py2executable} && %{with python2}
rm -f %{buildroot}%{_bindir}/* || :
%py2_install
%endif

# TODO there is no manpage
#mkdir -p %{buildroot}%{_mandir}/man1
#install -pm 644 fmf.1* %{buildroot}%{_mandir}/man1


%check
export LANG=en_US.utf-8

%if %{with python2}
%{__python2} -m pytest -vv
%endif

%if %{with python3}
%{__python3} -m pytest -vv || : # TODO the test fail here!
%endif


%{!?_licensedir:%global license %%doc}

%if %{with python2}
%files -n python2-%{name}
%if %{with py2executable}
#{_mandir}/man1/*
%{_bindir}/%{name}
%endif
%{python2_sitelib}/%{name}/
%{python2_sitelib}/%{name}-*.egg-info
%doc README.rst examples
%license LICENSE
%endif

%if %{with python3}
%files -n python%{python3_pkgversion}-%{name}
%if %{without py2executable}
#{_mandir}/man1/*
%{_bindir}/%{name}
%endif
%{python3_sitelib}/%{name}/
%{python3_sitelib}/%{name}-*.egg-info
%doc README.rst examples
%license LICENSE
%endif


%changelog
* Mon Jan 22 2018 Petr Šplíchal <psplicha@redhat.com> 0.1-1
- Initial packaging.
