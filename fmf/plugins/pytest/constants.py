CONFIG_POSTPROCESSING_TEST = "test_postprocessing"
PYTEST_DEFAULT_CONF = {
    CONFIG_POSTPROCESSING_TEST: {
        "test": """
cls_str = ("::" + str(cls.name)) if cls.name else ""
escaped = shlex.quote(f"{filename}{cls_str}::{test.name}")
f"python3 -m pytest -m '' -v {escaped}" """
        }
}
CONFIG_MERGE_PLUS = "merge_plus"
CONFIG_MERGE_MINUS = "merge_minus"
CONFIG_ADDITIONAL_KEY = "additional_keys"
CONFIG_POSTPROCESSING_TEST = "test_postprocessing"
