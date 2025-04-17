"""Module for loading and accessing environment variables from a .env file or StringIO.

This module provides functionality to load environment variables from a .env file
or StringIO object into os.environ and access them with type casting through a custom
Environ class. It supports type-hinted access to environment variables with automatic
conversion to specified types.

Public interfaces:
- load: Load environment variables from a file or StringIO.
- Environ: Base class for accessing environment variables with type casting.
- field: Decorator for defining environment variable fields with custom conversion.
"""

import os
from io import StringIO
from pathlib import Path
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Iterable,
    Optional,
    Union,
)

__all__ = ("load", "Environ", "field")


def load(arg: Optional[Union[Path, StringIO]] = None) -> None:
    """Load environment variables from a .env file or StringIO into os.environ.

    Args:
        arg: Path to a .env file or a StringIO object containing environment
            variables in KEY=VALUE format. If None, defaults to '.env' in the
            current directory.

    Raises:
        FileNotFoundError: If the specified .env file does not exist.

    Examples:
        >>> load()  # Loads from .env file
        >>> load(Path("custom.env"))  # Loads from custom.env
        >>> load(StringIO("KEY=VALUE\\n"))  # Loads from StringIO
    """
    if Environ.loaded:
        return

    Environ.loaded = True

    if arg is None:
        arg = Path(".env")

    if isinstance(arg, Path) and arg.exists():
        with arg.open() as env_file:
            _update_environ(env_file)
        return

    if isinstance(arg, StringIO):
        _update_environ(arg.readlines())
        return


class EnvironBase:
    """Base class for handling environment variables with support for prefixes and type hints.

    This class provides the foundation for environment variable management,
    including prefix support and type hint initialization for subclasses.
    """

    prefix: ClassVar[str] = ""

    @classmethod
    def __init_subclass__(cls, prefix="", **kwargs):
        super().__init_subclass__(**kwargs)
        cls.prefix = prefix


class Environ(EnvironBase, prefix=""):
    """Base class for accessing environment variables with type casting.

    Subclasses can define type-hinted class attributes to specify the expected
    types of environment variables. Accessing these attributes retrieves the
    corresponding environment variable and casts it to the annotated type.
    Uses an internal cache to store converted values and improve performance
    on repeated access.

    Raises:
        AttributeError: If the requested attribute is not defined in type hints.
        ValueError: If the environment variable is not found or cannot be converted
            to the specified type.

    Examples:
        >>> class MyEnviron(Environ):
        ...     DEBUG: bool
        ...     TIMEOUT: int
        >>> env = MyEnviron()
        >>> env.DEBUG  # Returns True if os.environ["DEBUG"] is "true" or "1"
        >>> env.TIMEOUT  # Returns int(os.environ["TIMEOUT"])
    """

    autoloaded: bool
    _cache: Dict[str, Any]

    loaded: ClassVar[bool] = False

    __slots__ = ("autoloaded", "_cache")

    def __init__(self, /, *, autoloaded: bool = True) -> None:
        """Initialize the Environ instance.

        Args:
            autoloaded: If True, automatically load environment variables from
                the default .env file upon instantiation. Optional parameter
                with default value `True`.
        """
        if autoloaded and not Environ.loaded:
            load()

        self.autoloaded = autoloaded
        self._cache = {}

    def __getattribute__(self, key: str, /) -> Any:
        """Intercept attribute access to provide type-converted environment variables.

        Overrides attribute access to retrieve environment variables, apply type
        conversions based on type hints, and cache the results for improved
        performance on subsequent accesses.

        Args:
            key: The name of the attribute being accessed.

        Returns:
            The converted value of the environment variable.

        Raises:
            AttributeError: If the attribute is not defined in type hints.
            ValueError: If the environment variable is missing or cannot be converted.
        """
        cache = object.__getattribute__(self, "_cache")
        if key in cache:
            return cache[key]

        klass = object.__getattribute__(self, "__class__")
        type_hints = object.__getattribute__(klass, "__annotations__")

        if key not in type_hints:
            return super().__getattribute__(key)

        type_hint = type_hints[key]

        field = getattr(klass, key, None)

        if field is None:
            prefix = object.__getattribute__(self, "prefix")
            try:
                str_value = os.environ[f"{prefix}{key}"]
            except KeyError as error:
                raise ValueError(
                    f"Environment variable '{key}' not found"
                ) from error

            field = _field_map.get(type_hint, lambda s: s)
            try:
                value = field(str_value)
            except Exception as error:
                raise ValueError(
                    f"Cannot convert '{str_value}' to {type_hint.__name__}"
                ) from error
        else:
            if callable(field):
                try:
                    str_value = os.environ[f"{self.prefix}{key}"]
                except KeyError as error:
                    raise ValueError(
                        f"Environment variable '{key}' not found"
                    ) from error

                value = field(str_value)
            else:
                pkey = f"{self.prefix}{key}"
                value = (
                    _field_map.get(type_hint, lambda s: s)(os.environ[pkey])
                    if pkey in os.environ
                    else field
                )

        if not isinstance(value, type_hint):
            raise ValueError(
                f"Expected type '{type_hint.__name__}' for '{key}', "
                f"but got '{type(value).__name__}'"
            )

        cache[key] = value

        return value


def field(call: Callable[[Any], Any]) -> Any:
    """Decorator for defining custom conversion logic for environment variables.

    Used in Environ subclasses to specify custom conversion functions for
    environment variable values. The decorated function is used to convert the
    string value before applying the type hint. The decorated function must
    accept a string and return the type expected by the type hint.

    Args:
        call: A callable that converts a string to the desired type.

    Returns:
        The callable itself, used as a marker for custom conversion.

    Examples:
        >>> class MyEnviron(Environ):
        ...     @field
        ...     def CUSTOM_FIELD(self, value: str) -> list:
        ...         return value.split(",")
        ...     CUSTOM_FIELD: list
        >>> env = MyEnviron()
        >>> env.CUSTOM_FIELD  # Converts os.environ["CUSTOM_FIELD"] to a list
    """
    return call


def default(value: Any) -> Any:
    return lambda obj_value: value if obj_value is None else obj_value


def _update_environ(lines: Iterable[str]) -> None:
    """Parse lines and update os.environ with KEY=VALUE pairs.

    Skips empty lines and comments (lines starting with '#').

    Args:
        lines: Iterable of strings in KEY=VALUE format.

    Raises:
        ValueError: If a line does not contain an '=' sign.
    """
    for line in lines:
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        if "=" not in line:
            raise ValueError(f"Invalid line in .env file: {line}")
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


def _bool_field_map(s: str) -> bool:
    """Convert a string to a boolean based on common values like 'true', '1', etc.

    Args:
        s: The string to convert.

    Returns:
        True if the string represents a truthy value, False otherwise.
    """
    s = s.lower()
    return s in ("true", "1", "yes", "on", "y")


_field_map = {
    bool: _bool_field_map,
    int: int,
    float: float,
    str: str,
    list: lambda s: s.split(","),
    tuple: lambda s: tuple(s.split(",")),
}
