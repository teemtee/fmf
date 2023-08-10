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
from pathlib import Path

import click
from click_option_group import optgroup

import fmf
import fmf.utils as utils

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Common option groups
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def _select_options(func):
    """Select group options"""

    @optgroup.group("Select")
    @optgroup.option("--key", "keys", metavar="KEY", default=[], multiple=True,
                     help="Key content definition (required attributes)")
    @optgroup.option("--name", "names", metavar="NAME", default=[], multiple=True,
                     help="List objects with name matching regular expression")
    @optgroup.option("--source", "sources", metavar="SOURCE", default=[], multiple=True,
                     help="List objects defined in specified source files")
    @optgroup.option("--filter", "filters", metavar="FILTER", default=[], multiple=True,
                     help="Apply advanced filter (see 'pydoc fmf.filter')")
    @optgroup.option("--condition", "conditions", metavar="EXPR", default=[], multiple=True,
                     help="Use arbitrary Python expression for filtering")
    @optgroup.option("--whole", is_flag=True, default=False,
                     help="Consider the whole tree (leaves only by default)")
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Hack to group the options into one variable
        select = {
            opt: kwargs.pop(opt)
            for opt in ("keys", "names", "sources", "filters", "conditions", "whole")
            }
        return func(*args, select=select, **kwargs)

    return wrapper


def _format_options(func):
    """Formating group options"""

    @optgroup.group("Format")
    @optgroup.option("--format", "formatting", metavar="FORMAT", default=None,
                     help="Custom output format using the {} expansion")
    @optgroup.option("--value", "values", metavar="VALUE", default=[], multiple=True,
                     help="Values for the custom formatting string")
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Hack to group the options into one variable
        format = {
            opt: kwargs.pop(opt)
            for opt in ("formatting", "values")
            }
        return func(*args, format=format, **kwargs)

    return wrapper


def _utils_options(func):
    """Utilities group options"""

    @optgroup.group("Utils")
    @optgroup.option("--path", "paths", metavar="PATH", multiple=True,
                     type=Path, default=["."],
                     show_default="current directory",
                     help="Path to the metadata tree")
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class CatchAllExceptions(click.Group):
    def __call__(self, *args, **kwargs):
        # TODO: This actually has no effect
        try:
            return self.main(*args, **kwargs)
        except fmf.utils.GeneralError as error:
            # TODO: Better handling of --debug
            if "--debug" not in kwargs:
                fmf.utils.log.error(error)
            raise


@click.group("fmf", cls=CatchAllExceptions)
@click.version_option(fmf.__version__, message="%(version)s")
@click.option("--verbose", is_flag=True, default=False, type=bool,
              help="Print information about parsed files to stderr")
@click.option("--debug", "-d", count=True, default=0, type=int,
              help="Provide debugging information. Repeat to see more details.")
@click.pass_context
def main(ctx, debug, verbose) -> None:
    """This is command line interface for the Flexible Metadata Format."""
    ctx.ensure_object(dict)
    if debug:
        utils.log.setLevel(debug)
    ctx.obj["verbose"] = verbose
    ctx.obj["debug"] = debug


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Sub-commands
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@main.command("ls")
@_select_options
@_utils_options
@click.pass_context
def ls(ctx, paths, select) -> None:
    """List names of available objects"""
    _show(ctx, paths, select, brief=True)


@main.command("clean")
def clean() -> None:
    """Remove cache directory and its content"""
    _clean()


@main.command("show")
@_select_options
@_format_options
@_utils_options
@click.pass_context
def show(ctx, paths, select, format) -> None:
    """Show metadata of available objects"""
    _show(ctx, paths, select, format_opts=format, brief=False)


@main.command("init")
@_utils_options
def init(paths) -> None:
    """Initialize a new metadata tree"""
    # For each path create an .fmf directory and version file
    for path in paths:
        root = fmf.Tree.init(path)
        click.echo("Metadata tree '{0}' successfully initialized.".format(root))


def _show(ctx, paths, select_opts, format_opts=None, brief=False):
    """ Show metadata for each path given """
    output = []
    for path in paths:
        if ctx.obj["verbose"]:
            utils.info("Checking {0} for metadata.".format(path))
        tree = fmf.Tree(path)
        for node in tree.prune(**select_opts):
            if brief:
                show = node.show(brief=True)
            else:
                assert format_opts is not None
                show = node.show(brief=False, **format_opts)
            # List source files when in debug mode
            if ctx.obj["debug"]:
                for source in node.sources:
                    show += utils.color("{0}\n".format(source), "blue")
            if show is not None:
                output.append(show)

    # Print output and summary
    if brief or format_opts and format_opts["formatting"]:
        joined = "".join(output)
    else:
        joined = "\n".join(output)
    click.echo(joined, nl=False)
    if ctx.obj["verbose"]:
        utils.info("Found {0}.".format(
            utils.listed(len(output), "object")))


def _clean():
    """Remove cache directory"""
    try:
        cache = utils.get_cache_directory(create=False)
        utils.clean_cache_directory()
        click.echo("Cache directory '{0}' has been removed.".format(cache))
    except Exception as error:  # pragma: no cover
        utils.log.error(
            "Unable to remove cache, exception was: {0}".format(error))
