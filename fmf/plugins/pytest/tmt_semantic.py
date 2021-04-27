import inspect
import shlex
import unittest

from fmf.utils import GeneralError

TEST_METHOD_PREFIX = "test"
FMF_ATTR_PREFIX = "__fmf_"
FMF_POSTFIX_MARKS = ("+", "-", "")
SUMMARY_KEY = "summary"
DESCRIPTION_KEY = "description"
ENVIRONMENT_KEY = "environment"
_ = shlex

TMT_ATTRIBUTES = {
    SUMMARY_KEY: str,
    DESCRIPTION_KEY: str,
    "order": int,
    "adjust": (
        list,
        dict,
        ),
    "tag": (
        list,
        str,
        ),
    "link": (list, str, dict),
    "duration": str,
    "tier": str,
    "component": (
        list,
        str,
        ),
    "require": (
        list,
        str,
        dict,
        ),
    "test": (str,),
    "framework": (str,),
    ENVIRONMENT_KEY: (
        dict,
        str,
        ),
    "path": (str,),
    "enabled": (bool,),
}


def fmf_prefixed_name(name):
    return FMF_ATTR_PREFIX + name


class __TMTMeta(type):
    @staticmethod
    def _set_fn(name, base_type=None):
        if name not in TMT_ATTRIBUTES:
            raise GeneralError(
                "fmf decorator {} not found in {}".format(
                    name, TMT_ATTRIBUTES.keys()))

        def inner(*args, post_mark=""):
            return generic_metadata_setter(
                fmf_prefixed_name(name),
                args,
                base_type=base_type or TMT_ATTRIBUTES[name],
                post_mark=post_mark,
                )

        return inner

    def __getattr__(cls, name):
        return cls._set_fn(name)


class TMT(metaclass=__TMTMeta):
    """
    This class implements class decorators for TMT semantics via dynamic class methods
    see https://tmt.readthedocs.io/en/latest/spec/tests.html
    """

    @classmethod
    def tag(cls, *args, post_mark=""):
        """
        generic purpose test tags to be used (e.g. "slow", "fast", "security")
        https://tmt.readthedocs.io/en/latest/spec/tests.html#tag
        """
        return cls._set_fn("tag", base_type=TMT_ATTRIBUTES["tag"])(
            *args, post_mark=post_mark
            )

    @classmethod
    def link(cls, *args, post_mark=""):
        """
        generic url links (default is verify) but could contain more see TMT doc
        https://tmt.readthedocs.io/en/latest/spec/core.html#link
        """
        return cls._set_fn("link", base_type=TMT_ATTRIBUTES["link"])(
            *args, post_mark=post_mark
            )

    @classmethod
    def bug(cls, *args, post_mark=""):
        """
        link to relevant bugs what this test verifies.
        It can be link to issue tracker or bugzilla
        https://tmt.readthedocs.io/en/latest/spec/tests.html#link
        """
        return cls.link(
            *[{"verifies": arg} for arg in args],
            post_mark=post_mark)

    @classmethod
    def adjust(
            cls, when, because=None, continue_execution=True, post_mark="", **
            kwargs):
        """
        adjust testcase execution, see TMT specification
        https://tmt.readthedocs.io/en/latest/spec/core.html#adjust

        if key value arguments are passed they are applied as update of the dictionary items
        else disable test execution as default option

        e.g.

        @adjust("distro ~< centos-6", "The test is not intended for less than centos-6")
        @adjust("component == bash", "modify component", component="shell")

        tricky example with passing merging variables as kwargs to code
        because python does not allow to do parameter as X+="something"
        use **dict syntax for parameter(s)

        @adjust("component == bash", "append env variable", **{"environment+": {"BASH":true}})
        """
        adjust_item = dict()
        adjust_item["when"] = when
        if because is not None:
            adjust_item["because"] = because
        if kwargs:
            adjust_item.update(kwargs)
        else:
            adjust_item["enabled"] = False
        if continue_execution is False:
            adjust_item["continue"] = False
        return cls._set_fn("adjust", base_type=TMT_ATTRIBUTES["adjust"])(
            adjust_item, post_mark=post_mark
            )

    @classmethod
    def environment(cls, post_mark="", **kwargs):
        """
        environment testcase execution, see TMT specification
        https://tmt.readthedocs.io/en/latest/spec/test.html#environment

        add environment keys
        example:
        @environment(PYTHONPATH=".", DATA_DIR="test_data")
        """
        return cls._set_fn(
            ENVIRONMENT_KEY, base_type=TMT_ATTRIBUTES[ENVIRONMENT_KEY])(
            kwargs, post_mark=post_mark)


def is_test_function(member):
    return inspect.isfunction(member) and member.__name__.startswith(
        TEST_METHOD_PREFIX)


def __set_method_attribute(item, attribute, value, post_mark, base_type=None):
    if post_mark not in FMF_POSTFIX_MARKS:
        raise GeneralError(
            "as postfix you can use + or - or let it empty (FMF merging)")
    attr_postfixed = attribute + post_mark
    for postfix in set(FMF_POSTFIX_MARKS) - {post_mark}:
        if hasattr(item, attribute + postfix):
            raise GeneralError(
                "you are mixing various post_marks for {} ({} already exists)".format(
                    item, attribute + postfix))
    if base_type is None:
        if isinstance(value, list) or isinstance(value, tuple):
            base_type = (list,)
        elif isinstance(value, dict):
            base_type = dict
            value = [value]
        else:
            value = [value]

    if isinstance(base_type, tuple) and base_type[0] in [tuple, list]:
        if not hasattr(item, attr_postfixed):
            setattr(item, attr_postfixed, list())
        # check expected object types for FMF attributes
        for value_item in value:
            if len(base_type) > 1 and not isinstance(
                    value_item, tuple(base_type[1:])):
                raise GeneralError(
                    "type {} (value:{}) is not allowed, please use: {} ".format(
                        type(value_item), value_item, base_type[1:]
                        )
                    )
        getattr(item, attr_postfixed).extend(list(value))
        return

    # use just first value in case you don't use list of tuple
    if len(value) > 1:
        raise GeneralError(
            "It is not permitted for {} (type:{}) put multiple values ({})".format(
                attribute, base_type, value))
    first_value = value[0]
    if base_type and not isinstance(first_value, base_type):
        raise GeneralError(
            "type {} (value:{}) is not allowed, please use: {} ".format(
                type(first_value), first_value, base_type
                )
            )
    if base_type in [dict]:
        if not hasattr(item, attr_postfixed):
            setattr(item, attr_postfixed, dict())
        first_value.update(getattr(item, attr_postfixed))
    if hasattr(item, attr_postfixed) and base_type not in [dict]:
        # if it is already defined (not list types or dict) exit
        # class decorators are applied right after, does not make sense to rewrite more specific
        # dict updating is reversed
        return
    setattr(item, attr_postfixed, first_value)


def set_obj_attribute(
    testEntity,
    attribute,
    value,
    raise_text=None,
    base_class=unittest.TestCase,
    base_type=None,
    post_mark="",
):
    if inspect.isclass(testEntity) and issubclass(testEntity, base_class):
        for test_function in inspect.getmembers(testEntity, is_test_function):
            __set_method_attribute(
                test_function[1],
                attribute,
                value,
                post_mark=post_mark,
                base_type=base_type,
                )
    elif is_test_function(testEntity):
        __set_method_attribute(
            testEntity, attribute, value, base_type=base_type,
            post_mark=post_mark)
    elif raise_text:
        raise GeneralError(raise_text)
    return testEntity


def generic_metadata_setter(
    attribute,
    value,
    raise_text=None,
    base_class=unittest.TestCase,
    base_type=None,
    post_mark="",
):
    def inner(testEntity):
        return set_obj_attribute(
            testEntity,
            attribute,
            value,
            raise_text,
            base_class,
            base_type=base_type,
            post_mark=post_mark,
            )

    return inner
