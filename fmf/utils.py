""" Logging, config, constants & utilities """

import copy
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import warnings
from io import StringIO
from pprint import pformat as pretty
from typing import Any, List, NamedTuple

from filelock import FileLock, Timeout
from ruamel.yaml import YAML, scalarstring
from ruamel.yaml.comments import CommentedMap

import fmf.base

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Constants
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Coloring
COLOR_ON = 1
COLOR_OFF = 0
COLOR_AUTO = 2

# Logging
LOG_ERROR = logging.ERROR
LOG_WARN = logging.WARN
LOG_INFO = logging.INFO
LOG_DEBUG = logging.DEBUG
LOG_CACHE = 7
LOG_DATA = 4
LOG_ALL = 1

# Current metadata format version
VERSION = 1

# Cache expiration in seconds
CACHE_EXPIRATION = 1200
# Placeholder for customized location
_CACHE_DIRECTORY = None

# Lock timeout in seconds for fetch
FETCH_LOCK_TIMEOUT = 5 * 60
# Maximum seconds to process fmf structure + possibly fetch the repo
NODE_LOCK_TIMEOUT = 60 + FETCH_LOCK_TIMEOUT

# Suffix of lock file for reading
LOCK_SUFFIX_READ = '.read.lock'
# Suffix of lock file for fetching
LOCK_SUFFIX_FETCH = '.fetch.lock'


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Exceptions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class GeneralError(Exception):
    """ General error """


class FormatError(GeneralError):
    """ Metadata format error """


class FileError(GeneralError):
    """ File reading error """


class RootError(FileError):
    """ Metadata tree root missing """


class FilterError(GeneralError):
    """ Missing data when filtering """


class MergeError(GeneralError):
    """ Unable to merge data between parent and child """


class ReferenceError(GeneralError):
    """ Referenced tree node cannot be found """


class FetchError(GeneralError):
    """ Fatal error in helper command while fetching """
    # Keep previously used format of the message

    def __str__(self):
        return self.args[0] if self.args else ''


class JsonSchemaError(GeneralError):
    """ Invalid JSON Schema """


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Utils
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def pluralize(singular=None):
    """ Naively pluralize words """
    if singular.endswith("y") and not singular.endswith("ay"):
        plural = singular[:-1] + "ies"
    elif singular.endswith("s"):
        plural = singular + "es"
    else:
        plural = singular + "s"
    return plural


def listed(items, singular=None, plural=None, max=None, quote="", join="and"):
    """
    Convert an iterable into a nice, human readable list or description::

        listed(range(1)) .................... 0
        listed(range(2)) .................... 0 and 1
        listed(range(3), join='or') ......... 0, 1 or 2
        listed(range(3), quote='"') ......... "0", "1" and "2"
        listed(range(4), max=3) ............. 0, 1, 2 and 1 more
        listed(range(5), 'number', max=3) ... 0, 1, 2 and 2 more numbers
        listed(range(6), 'category') ........ 6 categories
        listed(7, "leaf", "leaves") ......... 7 leaves

    If singular form is provided but max not set the description-only
    mode is activated as shown in the last two examples. Also, an int
    can be used in this case to get a simple inflection functionality.
    """

    # Convert items to list if necessary
    items = range(items) if isinstance(items, int) else list(items)
    more = " more"
    # Description mode expected when singular provided but no maximum set
    if singular is not None and max is None:
        max = 0
        more = ""
    # Set the default plural form
    if singular is not None and plural is None:
        plural = pluralize(singular)
    # Convert to strings and optionally quote each item
    items = ["{0}{1}{0}".format(quote, item) for item in items]

    # Select the maximum of items and describe the rest if max provided
    if max is not None:
        # Special case when the list is empty (0 items)
        if max == 0 and len(items) == 0:
            return "0 {0}".format(plural)
        # Cut the list if maximum exceeded
        if len(items) > max:
            rest = len(items[max:])
            items = items[:max]
            if singular is not None:
                more += " {0}".format(singular if rest == 1 else plural)
            items.append("{0}{1}".format(rest, more))

    # For two and more items use 'and' instead of the last comma
    if len(items) < 2:
        return "".join(items)
    else:
        return ", ".join(items[0:-2] + [' {} '.format(join).join(items[-2:])])


def split(values, separator=re.compile("[ ,]+")):
    """
    Convert space-or-comma-separated values into a single list

    Common use case for this is merging content of options with multiple
    values allowed into a single list of strings thus allowing any of
    the formats below and converts them into ['a', 'b', 'c']::

        --option a --option b --option c ... ['a', 'b', 'c']
        --option a,b --option c ............ ['a,b', 'c']
        --option 'a b c' ................... ['a b c']

    Accepts both string and list. By default space and comma are used as
    value separators. Use any regular expression for custom separator.
    """
    if not isinstance(values, list):
        values = [values]
    return sum([separator.split(value) for value in values], [])


def info(message, newline=True):
    """ Log provided info message to the standard error output """
    sys.stderr.write(message + ("\n" if newline else ""))


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Filtering
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def evaluate(expression, data, _node=None):
    """
    Evaluate arbitrary Python expression against given data

    Expects data dictionary which will be used to populate local
    namespace. Used to provide flexible conditions for filtering.
    """
    locals().update(data)
    try:
        return eval(expression)
    except NameError as error:
        raise FilterError("Key is not defined in data: {}".format(error))
    except KeyError as error:
        raise FilterError("Internal key is not defined: {}".format(error))


def filter(filter, data, sensitive=True, regexp=False):
    """
    Return true if provided filter matches given dictionary of values

    Filter supports disjunctive normal form with '|' used for OR, '&'
    for AND and '-' for negation. Individual values are prefixed with
    'value:', leading/trailing white-space is stripped. For example::

        tag: Tier1 | tag: Tier2 | tag: Tier3
        category: Sanity, Security & tag: -destructive

    Note that multiple comma-separated values can be used as a syntactic
    sugar to shorten the filter notation::

        tag: A, B, C ---> tag: A | tag: B | tag: C

    Values should be provided as a dictionary of lists each describing
    the values against which the filter is to be matched. For example::

        data = {tag: ["Tier1", "TIPpass"], category: ["Sanity"]}

    Other types of dictionary values are converted into a string.
    A FilterError exception is raised when a dimension parsed from the
    filter is not found in the data dictionary. Set option 'sensitive'
    to False to enable case-insensitive matching. If 'regexp' option is
    True, regular expressions can be used in the filter values as well.
    """

    def match_value(pattern, text):
        """ Match value against data (simple or regexp) """
        if regexp:
            return re.match("^{0}$".format(pattern), text)
        else:
            return pattern == text

    def check_value(dimension, value):
        """ Check whether the value matches data """
        # E.g. value = 'A, B' or value = "C" or value = "-D"
        # If there are multiple values, at least one must match
        for atom in re.split(r"\s*,\s*", value):
            # Handle negative values (check the whole data for non-presence)
            if atom.startswith("-"):
                atom = atom[1:]
                # Check each value for given dimension
                for dato in data[dimension]:
                    if match_value(atom, dato):
                        break
                # Pattern not found ---> good
                else:
                    return True
            # Handle positive values (return True upon first successful match)
            else:
                # Check each value for given dimension
                for dato in data[dimension]:
                    if match_value(atom, dato):
                        # Pattern found ---> good
                        return True
        # No value matched the data
        return False

    def check_dimension(dimension, values):
        """ Check whether all values for given dimension match data """
        # E.g. dimension = 'tag', values = ['A, B', 'C', '-D']
        # Raise exception upon unknown dimension
        if dimension not in data:
            raise FilterError("Invalid filter '{0}'".format(dimension))
        # Every value must match at least one value for data
        return all([check_value(dimension, value) for value in values])

    def check_clause(clause):
        """ Split into literals and check whether all match """
        # E.g. clause = 'tag: A, B & tag: C & tag: -D'
        # Split into individual literals by dimension
        literals = dict()
        for literal in re.split(r"\s*&\s*", clause):
            # E.g. literal = 'tag: A, B'
            # Make sure the literal matches dimension:value format
            matched = re.match(r"^([^:]*)\s*:\s*(.*)$", literal)
            if not matched:
                raise FilterError("Invalid filter '{0}'".format(literal))
            dimension, value = matched.groups()
            values = [value]
            # Append the literal value(s) to corresponding dimension list
            literals.setdefault(dimension, []).extend(values)
        # For each dimension all literals must match given data
        return all([check_dimension(dimension, values)
                    for dimension, values in literals.items()])

    # Default to True if no filter given, bail out if weird data given
    if filter is None or filter == "":
        return True
    if not isinstance(data, dict):
        raise FilterError("Invalid data type '{0}'".format(type(data)))

    # Make sure that data dictionary contains lists of strings
    data = copy.deepcopy(data)
    for key in data:
        if isinstance(data[key], list):
            data[key] = [str(item) for item in data[key]]
        else:
            data[key] = [str(data[key])]
    # Turn all data into lowercase if sensitivity is off
    if not sensitive:
        filter = filter.lower()
        lowered = dict()
        for key, values in data.items():
            lowered[key.lower()] = [value.lower() for value in values]
        data = lowered

    # At least one clause must be true
    return any([check_clause(clause)
                for clause in re.split(r"\s*\|\s*", filter)])

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Logging
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class Logging:
    """ Logging Configuration """

    # Color mapping
    COLORS = {
        LOG_ERROR: "red",
        LOG_WARN: "yellow",
        LOG_INFO: "blue",
        LOG_DEBUG: "green",
        LOG_CACHE: "cyan",
        LOG_DATA: "magenta",
        }
    # Environment variable mapping
    MAPPING = {
        0: LOG_WARN,
        1: LOG_INFO,
        2: LOG_DEBUG,
        3: LOG_CACHE,
        4: LOG_DATA,
        5: LOG_ALL,
        }
    # All levels
    LEVELS = "CRITICAL DEBUG ERROR FATAL INFO NOTSET WARN WARNING".split()

    # Default log level is WARN
    _level = LOG_WARN

    # Already initialized loggers by their name
    _loggers = dict()

    def __init__(self, name='fmf'):
        # Use existing logger if already initialized
        try:
            self.logger = Logging._loggers[name]
        # Otherwise create a new one, save it and set it
        except KeyError:
            self.logger = self._create_logger(name=name)
            Logging._loggers[name] = self.logger
            self.set()

    class ColoredFormatter(logging.Formatter):
        """ Custom color formatter for logging """

        def format(self, record):
            # Handle custom log level names
            if record.levelno == LOG_ALL:
                levelname = "ALL"
            elif record.levelno == LOG_DATA:
                levelname = "DATA"
            elif record.levelno == LOG_CACHE:
                levelname = "CACHE"
            else:
                levelname = record.levelname
            # Map log level to appropriate color
            try:
                colour = Logging.COLORS[record.levelno]
            except KeyError:
                colour = "black"
            # Color the log level, use brackets when coloring off
            if Coloring().enabled():
                level = color(" " + levelname + " ", "lightwhite", colour)
            else:
                level = "[{0}]".format(levelname)
            return u"{0} {1}".format(level, record.getMessage())

    @staticmethod
    def _create_logger(name='fmf', level=None):
        """ Create fmf logger """
        # Create logger, handler and formatter
        logger = logging.getLogger(name)
        handler = logging.StreamHandler()
        handler.setFormatter(Logging.ColoredFormatter())
        logger.addHandler(handler)
        # Save log levels in the logger itself (backward compatibility)
        for level in Logging.LEVELS:
            setattr(logger, level, getattr(logging, level))
        # Additional logging constants and methods for cache and xmlrpc
        logger.DATA = LOG_DATA
        logger.CACHE = LOG_CACHE
        logger.ALL = LOG_ALL
        logger.cache = lambda message: logger.log(LOG_CACHE, message)  # NOQA
        logger.data = lambda message: logger.log(LOG_DATA, message)  # NOQA
        logger.all = lambda message: logger.log(LOG_ALL, message)  # NOQA
        return logger

    def set(self, level=None):
        """
        Set the default log level

        If the level is not specified environment variable DEBUG is used
        with the following meaning::

            DEBUG=0 ... LOG_WARN (default)
            DEBUG=1 ... LOG_INFO
            DEBUG=2 ... LOG_DEBUG
            DEBUG=3 ... LOG_CACHE
            DEBUG=4 ... LOG_DATA
            DEBUG=5 ... LOG_ALL (log all messages)
        """
        # If level specified, use given
        if level is not None:
            Logging._level = level
        # Otherwise attempt to detect from the environment
        else:
            try:
                Logging._level = Logging.MAPPING[int(os.environ["DEBUG"])]
            except Exception:
                Logging._level = logging.WARN
        self.logger.setLevel(Logging._level)

    def get(self):
        """ Get the current log level """
        return self.logger.level


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Coloring
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def color(text, color=None, background=None, light=False, enabled="auto"):
    """
    Return text in desired color if coloring enabled

    Available colors: black red green yellow blue magenta cyan white.
    Alternatively color can be prefixed with "light", e.g. lightgreen.
    """
    colors = {"black": 30, "red": 31, "green": 32, "yellow": 33,
              "blue": 34, "magenta": 35, "cyan": 36, "white": 37}
    # Nothing do do if coloring disabled
    if enabled == "auto":
        enabled = Coloring().enabled()
    if not enabled:
        return text
    # Prepare colors (strip 'light' if present in color)
    if color and color.startswith("light"):
        light = True
        color = color[5:]
    color = color and ";{0}".format(colors[color]) or ""
    background = background and ";{0}".format(colors[background] + 10) or ""
    light = light and 1 or 0
    # Starting and finishing sequence
    start = "\033[{0}{1}{2}m".format(light, color, background)
    finish = "\033[1;m"
    return "".join([start, text, finish])


class Coloring:
    """ Coloring configuration """

    # Default color mode is auto-detected from the terminal presence
    _mode = None
    MODES = ["COLOR_OFF", "COLOR_ON", "COLOR_AUTO"]
    # We need only a single config instance
    _instance = None

    def __new__(cls, *args, **kwargs):
        """ Make sure we create a single instance only """
        if not cls._instance:
            cls._instance = super(Coloring, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, mode=None):
        """ Initialize the coloring mode """
        # Nothing to do if already initialized
        if self._mode is not None:
            return
        # Set the mode
        self.set(mode)

    def set(self, mode=None):
        """
        Set the coloring mode

        If enabled, some objects (like case run Status) are printed in color
        to easily spot failures, errors and so on. By default the feature is
        enabled when script is attached to a terminal. Possible values are::

            COLOR=0 ... COLOR_OFF .... coloring disabled
            COLOR=1 ... COLOR_ON ..... coloring enabled
            COLOR=2 ... COLOR_AUTO ... if terminal attached (default)

        Environment variable COLOR can be used to set up the coloring to the
        desired mode without modifying code.
        """
        # Detect from the environment if no mode given (only once)
        if mode is None:
            # Nothing to do if already detected
            if self._mode is not None:
                return
            # Detect from the environment variable COLOR
            try:
                mode = int(os.environ["COLOR"])
            except Exception:
                mode = COLOR_AUTO
        elif mode < 0 or mode > 2:
            raise RuntimeError("Invalid color mode '{0}'".format(mode))
        self._mode = mode
        log.debug(
            "Coloring {0} ({1})".format(
                "enabled" if self.enabled() else "disabled",
                self.MODES[self._mode]))

    def get(self):
        """ Get the current color mode """
        return self._mode

    def enabled(self):
        """ True if coloring is currently enabled """
        # In auto-detection mode color enabled when terminal attached
        if self._mode == COLOR_AUTO:
            return sys.stdout.isatty()
        return self._mode == COLOR_ON


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Cache directory
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_cache_directory(create=True):
    """
    Return cache directory, created by this call if necessary

    Cache directory is (first existing):
    - Value of FMF_CACHE_DIRECTORY environment variable
    - Value set by the last call of `set_cache_directory()`
    - $XDG_CACHE_HOME/fmf
    - ~/.cache/fmf

    Raise GeneralError if it is not possible to create it.
    """
    cache = (
        os.environ.get('FMF_CACHE_DIRECTORY', _CACHE_DIRECTORY)
        or os.path.join(
            os.path.expanduser(
                os.environ.get('XDG_CACHE_HOME', '~/.cache')),
            'fmf')
        )
    if not os.path.isdir(cache) and create:
        try:
            os.makedirs(cache, exist_ok=True)
        except OSError as error:
            raise GeneralError(
                "Failed to create cache directory '{0}'.".format(cache))
    return cache


def set_cache_directory(cache_directory):
    """ Set preferred cache directory """
    global _CACHE_DIRECTORY
    _CACHE_DIRECTORY = cache_directory


def set_cache_expiration(seconds):
    """ Seconds until cache expires """
    global CACHE_EXPIRATION
    CACHE_EXPIRATION = int(seconds)


def clean_cache_directory():
    """ Delete used cache directory if it exists """
    cache = get_cache_directory(create=False)
    if os.path.isdir(cache):
        shutil.rmtree(cache)


def invalidate_cache():
    """ Force fetch next time cache is used regardless its age """
    # Missing FETCH_HEAD means `git fetch` will happen
    cache = get_cache_directory(create=False)
    # Cache not exists, nothing to do
    if not os.path.isdir(cache):
        return  # pragma: no cover
    issues = []
    for root, dirs, files in os.walk(cache, topdown=True):
        if '.git' not in dirs:
            continue
        # Content of root is path to git repo
        fetch_head = os.path.join(root, '.git', 'FETCH_HEAD')
        try:
            if os.path.isfile(fetch_head):
                lock_path = root + LOCK_SUFFIX_FETCH
                log.debug("Remove '{0}'.".format(fetch_head))
                with FileLock(lock_path, timeout=FETCH_LOCK_TIMEOUT) as lock:
                    os.remove(fetch_head)
        except (IOError, Timeout) as error:  # pragma: no cover
            issues.append(
                "Couldn't remove file '{0}': {1}".format(fetch_head, error))
        # Already found a .git so no need to continue inside the root
        del dirs[:]
    if issues:  # pragma: no cover
        raise GeneralError("\n".join(issues))

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Fetch Tree from the Remote Repository
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def fetch_tree(url, ref=None, path='.'):
    """
    Get initialized Tree from a remote git repository

    url .... git repository url (required)
    ref .... branch, tag or commit (default branch if None)
    path ... metadata tree root (default to '.')

    See :meth:`fmf.base.Tree.node` to canonical default values.

    Remote repository is cached locally (see :func:`get_cache_directory`),
    local directory with cache is locked during reading.

    Raises GeneralError when lock couldn't be acquired.
    """
    # Create lock path to fetch/read git from URL to the cache
    cache_dir = get_cache_directory()
    # Use LOCK_SUFFIX_READ suffix (different from the inner fetch lock)
    lock_path = os.path.join(
        cache_dir, url.replace('/', '_')) + LOCK_SUFFIX_READ
    try:
        with FileLock(lock_path, timeout=NODE_LOCK_TIMEOUT) as lock:
            # Write PID to lockfile so we know which process got it
            with open(lock.lock_file, 'w') as lock_file:
                lock_file.write(str(os.getpid()))
            repository = fetch_repo(url, ref)
            root = os.path.join(repository, path)
            return fmf.base.Tree(root)
    except Timeout:
        raise GeneralError(
            "Failed to acquire lock for {0} within {1} seconds".format(
                lock_path, NODE_LOCK_TIMEOUT))


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Deprecated 'fetch' method (deprecated from 0.15)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def fetch(url, ref=None, destination=None, env=None):
    """ Deprecated: Use :func:`fetch_repo` instead """
    # DeprecationWarning is hidden by default (unless -Wall or -Wonce option)
    # so using FutureWarning to have this visible by default
    warnings.warn(
        "Use 'utils.fetch_repo()' instead, "
        "this method will be removed in the future.",
        FutureWarning, stacklevel=2)
    return fetch_repo(url, ref, destination, env)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Fetch Remote Repository
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def default_branch(repository, remote="origin"):
    """ Detect default branch from given local git repository """
    head = os.path.join(repository, f".git/refs/remotes/{remote}/HEAD")
    # Make sure the HEAD reference is available
    if not os.path.exists(head):
        run(["git", "remote", "set-head", remote, "--auto"], cwd=repository)
    # The ref format is 'ref: refs/remotes/origin/main'
    with open(head) as ref:
        return ref.read().strip().split('/')[-1]


def fetch_repo(url, ref=None, destination=None, env=None):
    """
    Fetch remote git repository and return local directory

    Fetch git repository from provided url into a local cache directory,
    checkout requested ref and return path to the repo. If no ref is
    provided, the default branch from the origin is used. If destination
    directory is provided, it should not exist or needs to be empty. Use
    dictionary env to set environment variables for git calls.

    Raises FetchError upon failure with the original exception included.
    """

    if destination is None:
        # Prepare the destination path
        cache = get_cache_directory()
        directory = url.replace('/', '_')
        destination = os.path.join(cache, directory)
    else:
        cache = os.path.dirname(destination.rstrip('/'))

    # Lock for possibly shared cache directory. Add the extension
    # LOCK_SUFFIX_FETCH manually in the constructor. Everything under
    # the with statement to correctly remove lock upon exception.
    log.debug("Acquire lock for '{0}'.".format(destination))
    try:
        lock_path = destination + LOCK_SUFFIX_FETCH
        with FileLock(lock_path, timeout=FETCH_LOCK_TIMEOUT) as lock:
            # Write PID to lockfile so we know which process got it
            with open(lock.lock_file, 'w') as lock_file:
                lock_file.write(str(os.getpid()))
            # Clone the repository
            if not os.path.isdir(os.path.join(destination, '.git')):
                run(['git', 'clone', url, destination], cwd=cache, env=env)
            # Detect the default branch if 'ref' not provided
            if ref is None:
                ref = default_branch(destination)
            # Fetch changes if we are too old
            fetch_head_file = os.path.join(destination, '.git', 'FETCH_HEAD')
            try:
                age = time.time() - os.path.getmtime(fetch_head_file)
            except OSError:
                age = CACHE_EXPIRATION
            if age >= CACHE_EXPIRATION:
                run(['git', 'fetch'], cwd=destination)
            # Checkout branch
            run(['git', 'checkout', '-f', ref], cwd=destination, env=env)
            # Reset to origin to get possible changes but no exit code check
            # ref could be tag or commit where it is expected to fail
            run(['git', 'reset', '--hard', "origin/{0}".format(ref)],
                cwd=destination, check_exit_code=False, env=env)
    except Timeout:
        raise GeneralError(
            "Failed to acquire lock for '{0}' within {1} seconds.".format(
                destination, FETCH_LOCK_TIMEOUT))
    except (OSError, subprocess.CalledProcessError) as error:
        raise FetchError("{0}".format(error), error)

    return destination


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Run command
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def run(command, cwd=None, check_exit_code=True, env=None):
    """
    Run command and return a (stdout, stderr) tuple

    :command as list (name, arg1, arg2...)
    :cwd path to directory where to run the command
    :check_exit_code raise CalledProcessError if exit code is non-zero
    :env dictionary of the environment variables for the command
    """
    log.debug("Running command: '{0}'.".format(' '.join(command)))

    process = subprocess.Popen(
        command, cwd=cwd, env=env, universal_newlines=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    log.debug("stdout: {0}".format(stdout.strip()))
    log.debug("stderr: {0}".format(stderr.strip()))
    log.debug("exit_code: {0}{1}".format(
        process.returncode, ('' if check_exit_code else ' (ignored)')))
    if check_exit_code and process.returncode != 0:
        raise subprocess.CalledProcessError(
            process.returncode, ' '.join(command), output=stdout + stderr)
    return stdout, stderr


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Default Logger
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Create the default output logger
log = Logging('fmf').logger


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Convert dict to yaml
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def dict_to_yaml(data, width=None, sort=False):
    """ Convert dictionary into yaml """
    output = StringIO()

    # Set formatting options
    yaml = YAML()
    yaml.indent(mapping=4, sequence=4, offset=2)
    yaml.default_flow_style = False
    yaml.allow_unicode = True
    yaml.encoding = 'utf-8'
    yaml.width = width

    # Make sure that multiline strings keep the formatting
    data = copy.deepcopy(data)
    scalarstring.walk_tree(data)

    # Sort the data https://stackoverflow.com/a/40227545
    if sort:
        sorted_data = CommentedMap()
        for key in sorted(data):
            sorted_data[key] = data[key]
        data = sorted_data

    yaml.dump(data, output)
    return output.getvalue()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Validation
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class JsonSchemaValidationResult(NamedTuple):
    """ Represents JSON Schema validation result """

    result: bool
    errors: List[Any]
