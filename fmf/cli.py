"""
This is command line interface for the Flexible Metadata Format.

Available commands are::

    fmf ls      List identifiers of available objects
    fmf show    Show metadata of available objects
    fmf init    Initialize a new metadata tree
    fmf clean   Remove cache directory and its content

See online documentation for more details and examples:

    http://fmf.readthedocs.io/

Check also help message of individual commands for the full list
of available options.
"""

import functools
from collections.abc import Iterator
from contextlib import contextmanager
from os import chdir, getcwd
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar, Union, cast

import click
from click import Context
from click_option_group import optgroup

from fmf import Tree, __version__
from fmf.utils import (GeneralError, clean_cache_directory, color,
                       get_cache_directory, info, listed, log)

# import sys
# if sys.version_info < (3, 8):
#     from typing_extensions import ParamSpec, Concatenate
# else:
#     from typing import ParamSpec, Concatenate
# from typing_extensions import ParamSpec, Concatenate


# Typing
F = TypeVar('F', bound=Callable[..., Any])


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Common option groups
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _select_options(func: F) -> F:
    """Select group options"""

    # Type is not yet supported for click option groups
    # https://github.com/click-contrib/click-option-group/issues/49
    @optgroup.group('Select')
    @optgroup.option('--key', 'keys', metavar='KEY', default=[], multiple=True,
                     help='Key content definition (required attributes)')
    @optgroup.option("--name", 'names', metavar='NAME', default=[], multiple=True,
                     help="List objects with name matching regular expression")
    @optgroup.option("--source", 'sources', metavar='SOURCE', default=[], multiple=True,
                     help="List objects defined in specified source files")
    @optgroup.option("--filter", 'filters', metavar='FILTER', default=[], multiple=True,
                     help="Apply advanced filter (see 'pydoc fmf.filter')")
    @optgroup.option("--condition", 'conditions', metavar="EXPR", default=[], multiple=True,
                     help="Use arbitrary Python expression for filtering")
    @optgroup.option("--whole", is_flag=True, default=False,
                     help="Consider the whole tree (leaves only by default)")
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Hack to group the options into one variable
        select = {
            opt: kwargs.pop(opt)
            for opt in ('keys', 'names', 'sources', 'filters', 'conditions', 'whole')
            }
        return func(*args, select=select, **kwargs)

    # return wrapper
    return cast(F, wrapper)


def _format_options(func: F) -> F:
    """Format group options"""

    @optgroup.group('Format')
    @optgroup.option("--format", "formatting", metavar="FORMAT", default=None,
                     help="Custom output format using the {} expansion")
    @optgroup.option("--value", "values", metavar="VALUE", default=[], multiple=True,
                     help="Values for the custom formatting string")
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Hack to group the options into one variable
        format = {
            opt: kwargs.pop(opt)
            for opt in ('formatting', 'values')
            }
        return func(*args, format=format, **kwargs)

    return cast(F, wrapper)


def _utils_options(func: F) -> F:
    """Utils group options"""

    @optgroup.group('Utils')
    @optgroup.option("--path", "paths", metavar="PATH", multiple=True,
                     type=Path, default=["."],
                     show_default='current directory',
                     help="Path to the metadata tree")
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return cast(F, wrapper)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class CatchAllExceptions(click.Group):

    def __call__(self, *args, **kwargs):
        try:
            return self.main(*args, **kwargs)
        except Exception as err:
            raise GeneralError("fmf cli command failed") from err


@click.group("fmf", cls=CatchAllExceptions)
@click.version_option(__version__, message="%(version)s")
@click.option("--verbose", is_flag=True, default=False, type=bool,
              help="Print information about parsed files to stderr")
@click.option("--debug", "-d", count=True, default=0, type=int,
              help="Provide debugging information. Repeat to see more details.")
@click.pass_context
def main(ctx: Context, debug: int, verbose: bool) -> None:
    """This is command line interface for the Flexible Metadata Format."""
    ctx.ensure_object(dict)
    log.setLevel(debug)
    ctx.obj['verbose'] = verbose
    ctx.obj['debug'] = debug


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Sub-commands
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@main.command("ls")
@_select_options
@_utils_options
@click.pass_context
def ls(ctx: Context, paths: list[Path], select: dict[str, Any]) -> None:
    """List names of available objects"""
    _show(ctx, paths, select, brief=True)


@main.command("show")
@_select_options
@_format_options
@_utils_options
@click.pass_context
def show(ctx: Context, paths: list[Path], select: dict[str, Any], format: dict[str, Any]) -> None:
    """List names of available objects"""
    _show(ctx, paths, select, format_opts=format, brief=False)


@main.command("init")
@_utils_options
def init(paths: list[Path]) -> None:
    """Initialize a new metadata tree"""
    # For each path create an .fmf directory and version file
    for p in paths:
        root = Tree.init(str(p))
        click.echo(f"Metadata tree '{root}' successfully initialized.")


@main.command("clean")
def clean() -> None:
    """ Remove cache directory and its content """
    try:
        cache = get_cache_directory(create=False)
        clean_cache_directory()
        click.echo(f"Cache directory '{cache}' has been removed.")
    except Exception as err:  # pragma: no cover
        raise GeneralError("Unable to remove cache") from err


def _show(ctx: Context, paths: list[Path], select_opts: dict[str, Any],
          format_opts: Optional[dict[str, Any]] = None,
          brief: bool = False) -> None:
    """ Show metadata for each path given """
    output = []
    for p in paths:
        if ctx.obj['verbose']:
            info(f"Checking {p} for metadata.")
        tree = Tree(str(p))
        for node in tree.prune(**select_opts):
            if brief:
                show_out = node.show(brief=True)
            else:
                assert format_opts is not None
                show_out = node.show(brief=False, **format_opts)
            # List source files when in debug mode
            if ctx.obj['debug']:
                for source in node.sources:
                    show_out += color(f"{source}\n", "blue")
            if show_out is not None:
                output.append(show_out)

    # Print output and summary
    if brief or format_opts and format_opts['formatting']:
        joined = "".join(output)
    else:
        joined = "\n".join(output)
    click.echo(joined, nl=False)
    if ctx.obj['verbose']:
        info(f"Found {listed(len(output), 'object')}.")


@contextmanager
def cd(target: Union[str, Path]) -> Iterator[None]:
    """
    Manage cd in a pushd/popd fashion.

    Usage:

        with cd(tmpdir):
          do something in tmpdir
    """
    curdir = getcwd()
    chdir(target)
    try:
        yield
    finally:
        chdir(curdir)
