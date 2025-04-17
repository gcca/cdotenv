# cdotenv

A Python library for loading and accessing environment variables from `.env` files or `StringIO` with type casting. Licensed under GPL 3.

## Installation

```bash
pip install cdotenv
```

## Usage

### Loading Environment Variables

The `load` function loads environment variables into `os.environ` from a `.env` file, a custom file path, or a `StringIO` object.

- **Default** `.env` **file**:

  ```python
  from cdotenv import load
  load()  # Loads from .env in current directory
  ```

- **Custom file path**:

  ```python
  from cdotenv import load
  from pathlib import Path
  load(Path("custom.env"))
  ```

- **StringIO**:

  ```python
  from cdotenv import load
  from io import StringIO
  load(StringIO("KEY=VALUE\n"))
  ```

The `.env` file should contain `KEY=VALUE` pairs, with comments (`#`) and empty lines ignored:

```
# Comment
KEY1=VALUE1
KEY2=VALUE2
```

### Accessing Environment Variables with Type Casting

The `Environ` class allows type-hinted access to environment variables with automatic type conversion.

```python
from cdotenv import Environ

class MyEnviron(Environ):
    DEBUG: bool
    DATABASE_URL: str
    TIMEOUT: int
    SEED: float

env = MyEnviron()
print(env.DEBUG)  # True if os.environ["DEBUG"] = "true"
print(env.DATABASE_URL)  # str, e.g., "postgresql://user:pass@localhost/db"
print(env.TIMEOUT)  # int, e.g., 30
print(env.SEED)  # float, e.g., 42.5
```

- Raises `ValueError` if a variable is missing or cannot be converted to the specified type.
- Raises `AttributeError` for undefined attributes.

### Custom Type Conversion

Use the `field` decorator for custom conversion logic:

```python
from cdotenv import Environ, field

class MyEnviron(Environ):
    LIST: list = field(lambda x: x.split(","))

env = MyEnviron()
print(env.LIST)  # ["a", "b", "c"] if os.environ["LIST"] = "a,b,c"
```

- Raises `ValueError` if the converted value does not match the type hint.

## Error Handling

- **Missing variable**:

  ```python
  class MyEnviron(Environ):
      MISSING: str
  env = MyEnviron()
  env.MISSING  # Raises ValueError: "Environment variable 'MISSING' not found"
  ```

- **Invalid type conversion**:

  ```python
  os.environ["INVALID"] = "not_an_int"
  class MyEnviron(Environ):
      INVALID: int
  env = MyEnviron()
  env.INVALID  # Raises ValueError: "Cannot convert 'not_an_int' to int"
  ```

- **Invalid return type**:

  ```python
  os.environ["WRONG_TYPE"] = "a,b,c"
  class MyEnviron(Environ):
      WRONG_TYPE: int = field(lambda x: x.split(","))
  env = MyEnviron()
  env.WRONG_TYPE  # Raises ValueError: "Expected type 'int' for 'WRONG_TYPE', but got 'list'"
  ```

## Workflow

The following diagram illustrates the workflow for loading and accessing environment variables:

```mermaid
sequenceDiagram
    participant User
    participant cdotenv
    participant os.environ

    User->>cdotenv: load(arg)
    alt arg is None
        cdotenv->>cdotenv: Use Path(".env")
    else arg is Path
        cdotenv->>cdotenv: Open file
    else arg is StringIO
        cdotenv->>cdotenv: Read lines
    end
    cdotenv->>os.environ: _update_environ(lines)
    os.environ->>os.environ: Set KEY=VALUE pairs

    User->>cdotenv: Instantiate MyEnviron()
    User->>cdotenv: Access env.VARIABLE
    cdotenv->>cdotenv: Check type hints
    alt VARIABLE defined
        cdotenv->>os.environ: Get VARIABLE value
        alt Custom field
            cdotenv->>cdotenv: Apply custom conversion
        else
            cdotenv->>cdotenv: Apply type casting
        end
        cdotenv->>cdotenv: Validate type
        cdotenv-->>User: Return value
    else
        cdotenv-->>User: Raise AttributeError
    end
    alt VARIABLE missing
        cdotenv-->>User: Raise ValueError
    else Type conversion fails
        cdotenv-->>User: Raise ValueError
    end
```

## License

This project is licensed under the GNU General Public License v3.0 (GPL 3).
