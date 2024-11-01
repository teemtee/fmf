"""Compatibility layer for jsonschema validation."""

from typing import Any, Optional

import jsonschema
from jsonschema.validators import Draft4Validator


def get_validator(
        schema: Any,
        schema_store: Optional[dict[str, Any]] = None
        ) -> Draft4Validator:
    """Create a validator instance based on available jsonschema version."""
    # Validate schema is a dict
    if not isinstance(schema, dict):  # TODO remove once mypy/pyright is added
        from fmf.utils import JsonSchemaError
        raise JsonSchemaError(f'Invalid schema type: {type(schema)}. Schema must be a dictionary.')

    schema_store = schema_store or {}

    try:
        from jsonschema import validators
        from referencing import Registry, Resource
        from referencing.jsonschema import DRAFT4

        # Modern approach with referencing
        resources = []
        for uri, contents in schema_store.items():
            # Try to create resource from contents (will use $schema if present)
            try:
                resource = Resource.from_contents(contents)
            except Exception:
                # If that fails, explicitly create as Draft4
                resource = DRAFT4.create_resource(contents)
            resources.append((uri, resource))

        registry = Registry().with_resources(resources)

        # Create validator using Draft4 meta-schema
        validator_cls = validators.validator_for(schema, default=Draft4Validator)
        return validator_cls(schema=schema, registry=registry)

    except ImportError:
        # Legacy approach with RefResolver
        try:
            resolver = jsonschema.RefResolver.from_schema(
                schema, store=schema_store)
        except AttributeError as error:
            from fmf.utils import JsonSchemaError
            raise JsonSchemaError(f'Provided schema cannot be loaded: {error}')
        return Draft4Validator(schema, resolver=resolver)
