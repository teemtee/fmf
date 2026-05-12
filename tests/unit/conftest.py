import pytest

from fmf.context import Context, ContextDimension, DefaultContextDimension


@pytest.fixture(scope="function")
def custom_context_cls() -> type[Context]:

    class TestDefaultContextDimension(DefaultContextDimension):
        pass

    class TestContextDimension(ContextDimension):
        _registrar = {}
        _default_dimension_cls = TestDefaultContextDimension

    class TestContext(Context):
        _context_dimensions = TestContextDimension

    return TestContext


@pytest.fixture(scope="function")
def default_context_cls() -> type[Context]:
    return Context


@pytest.fixture(
    scope="function",
    params=["custom_context", "default_context"],
    )
def context_cls(
        request: pytest.FixtureRequest,
        custom_context_cls: type[Context],
        default_context_cls: type[Context]) -> type[Context]:
    # Note: it is inefficient to request both context classes, but I could not find
    # a better way around it, maybe someone in the future can find one.
    if request.param == "custom_context":
        return custom_context_cls
    elif request.param == "default_context":
        return default_context_cls
    raise NotImplementedError(f"Unknown ctx_id: {request.param}")
