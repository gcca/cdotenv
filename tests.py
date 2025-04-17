import os
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import mock_open, patch

from cdotenv.cdotenv import Environ, _update_environ, field, load


@patch.dict("os.environ", {}, clear=True)
class TestLoad(unittest.TestCase):

    def setUp(self):
        Environ.loaded = False

    def test_load_with_none_arg(self):
        with patch("pathlib.Path.open", mock_open(read_data="KEY=VALUE")):
            load()
            self.assertEqual(os.environ["KEY"], "VALUE")

    def test_load_with_path(self):
        mock_path = Path("test.env")
        with patch("pathlib.Path.exists", return_value=True), patch(
            "pathlib.Path.open", mock_open(read_data="KEY=VALUE")
        ):
            load(mock_path)
            self.assertEqual(os.environ["KEY"], "VALUE")

    def test_load_with_stringio(self):
        mock_stringio = StringIO("KEY=VALUE\n")
        load(mock_stringio)
        self.assertEqual(os.environ["KEY"], "VALUE")

    def test_update_environ_with_valid_lines(self):
        lines = ["KEY1=VALUE1", "KEY2=VALUE2"]
        _update_environ(lines)
        self.assertEqual(os.environ["KEY1"], "VALUE1")
        self.assertEqual(os.environ["KEY2"], "VALUE2")

    def test_update_environ_with_comments_and_empty_lines(self):
        lines = ["# Comment", "", "KEY=VALUE"]
        _update_environ(lines)
        self.assertEqual(os.environ["KEY"], "VALUE")
        self.assertEqual(len(os.environ), 1)

    def test_update_environ_with_invalid_lines(self):
        lines = ["MALFORMED"]
        with self.assertRaises(ValueError) as cm:
            _update_environ(lines)
        self.assertEqual(len(os.environ), 0)
        self.assertEqual(
            str(cm.exception), "Invalid line in .env file: MALFORMED"
        )

    def test_update_environ_with_malformed_lines(self):
        lines = ["KEY=VALUE", "ANOTHER=VALUE=WITH=EXTRA=EQUALS"]
        _update_environ(lines)
        self.assertEqual(os.environ["KEY"], "VALUE")
        self.assertEqual(os.environ["ANOTHER"], "VALUE=WITH=EXTRA=EQUALS")

    def test_update_environ_with_spaces(self):
        lines = ["  KEY  =  VALUE  "]
        _update_environ(lines)
        self.assertEqual(os.environ["KEY"], "VALUE")

    def test_update_environ_with_duplicate_keys(self):
        lines = ["KEY=VALUE1", "KEY=VALUE2"]
        _update_environ(lines)
        self.assertEqual(os.environ["KEY"], "VALUE2")

    def test_load_with_nonexistent_file(self):
        with patch(
            "pathlib.Path.open", side_effect=FileNotFoundError
        ), self.assertRaises(FileNotFoundError):
            load()

    def test_load_with_special_encoding(self):
        mock_path = Path("test.env")
        with patch("pathlib.Path.exists", return_value=True), patch(
            "pathlib.Path.open",
            mock_open(
                read_data="KEY=VALOR_ESPECIAL".encode("utf-8-sig").decode(
                    "utf-8"
                )
            ),
        ):
            load(mock_path)
            self.assertEqual(os.environ["\ufeffKEY"], "VALOR_ESPECIAL")

    def test_update_environ_with_special_characters(self):
        lines = ["VAR_CON_ESPACIO=valor", "VAR=CON=IGUAL=valor"]
        _update_environ(lines)
        self.assertIn("VAR_CON_ESPACIO", os.environ)
        self.assertIn("VAR", os.environ)


class TestEnviron(unittest.TestCase):

    def test_environ_type_casting(self):
        with patch.dict(
            "os.environ",
            {
                "DEBUG": "true",
                "URL": "postgresql://user:pass@localhost/db",
                "TIMEOUT": "30",
                "SEED": "42.5",
            },
            clear=True,
        ):

            class TestEnviron(Environ):
                DEBUG: bool
                URL: str
                TIMEOUT: int
                SEED: float

            env = TestEnviron()
            test_cases = [
                ("DEBUG", bool, True),
                ("URL", str, "postgresql://user:pass@localhost/db"),
                ("TIMEOUT", int, 30),
                ("SEED", float, 42.5),
            ]
            for attr, type_, expected in test_cases:
                with self.subTest(attr=attr):
                    value = getattr(env, attr)
                    self.assertIsInstance(value, type_)
                    self.assertEqual(value, expected)

    def test_environ_missing_variable(self):
        with patch.dict("os.environ", {}, clear=True):

            class TestEnviron(Environ):
                MISSING: str

            env = TestEnviron()
            with self.assertRaises(ValueError) as cm:
                _ = env.MISSING
            self.assertEqual(
                str(cm.exception), "Environment variable 'MISSING' not found"
            )

    def test_environ_invalid_type_conversion(self):
        with patch.dict("os.environ", {"INVALID": "not_an_int"}, clear=True):

            class TestEnviron(Environ):
                INVALID: int

            env = TestEnviron()
            with self.assertRaises(ValueError) as cm:
                _ = env.INVALID
            self.assertEqual(
                str(cm.exception), "Cannot convert 'not_an_int' to int"
            )

    def test_environ_undefined_attribute(self):
        with patch.dict("os.environ", {}, clear=True):

            class TestEnviron(Environ):
                DEBUG: bool

            env = TestEnviron()
            with self.assertRaises(AttributeError) as cm:
                _ = env.UNDEFINED
            self.assertEqual(
                str(cm.exception),
                "'TestEnviron' object has no attribute 'UNDEFINED'",
            )

    def test_field_custom_conversion(self):
        with patch.dict("os.environ", {"LIST": "a,b,c"}, clear=True):

            class TestEnviron(Environ):
                LIST: list = field(lambda x: x.split(","))

            env = TestEnviron()
            self.assertEqual(env.LIST, ["a", "b", "c"])

    def test_field_invalid_return_type(self):
        with patch.dict("os.environ", {"WRONG_TYPE": "a,b,c"}, clear=True):

            class TestEnviron(Environ):
                WRONG_TYPE: int = field(lambda x: x.split(","))

            env = TestEnviron()
            with self.assertRaises(ValueError) as cm:
                _ = env.WRONG_TYPE
            self.assertEqual(
                str(cm.exception),
                "Expected type 'int' for 'WRONG_TYPE', but got 'list'",
            )

    def test_environ_with_prefix(self):
        with patch.dict("os.environ", {"P_DEBUG": "true"}, clear=True):

            class PrefixedEnviron(Environ, prefix="P_"):
                DEBUG: bool

            env = PrefixedEnviron()
            self.assertTrue(env.DEBUG)

    def test_environ_tuple_conversion(self):
        with patch.dict("os.environ", {"TUPLE": "1,2,3"}, clear=True):

            class TestEnviron(Environ):
                TUPLE: tuple

            env = TestEnviron()
            self.assertEqual(env.TUPLE, ("1", "2", "3"))

    def test_environ_access_to_non_type_hinted_attribute(self):
        with patch.dict("os.environ", {}, clear=True):

            class TestEnviron(Environ):
                DEBUG: bool

            env = TestEnviron()
            with self.assertRaises(AttributeError):
                _ = env.NON_EXISTENT

    def test_environ_autoload(self):
        with (
            patch("pathlib.Path.open", mock_open(read_data="AUTOLOAD=YES")),
            patch.dict("os.environ", {}, clear=True),
        ):
            Environ.loaded = False

            class TestEnviron(Environ):
                AUTOLOAD: str

            env = TestEnviron(autoloaded=True)
            self.assertEqual(env.AUTOLOAD, "YES")

    def test_environ_no_reload_if_already_loaded(self):
        with (
            patch("pathlib.Path.open", mock_open(read_data="KEY=VALUE")),
            patch.dict("os.environ", {}, clear=True),
        ):
            load()
            Environ.loaded = True
            Environ(autoloaded=True)

    def test_field_conversion_exception(self):
        with patch.dict("os.environ", {"ERROR": "invalid"}, clear=True):

            class TestEnviron(Environ):
                ERROR: int = field(lambda x: int(x))

            env = TestEnviron()
            with self.assertRaises(ValueError):
                _ = env.ERROR

    def test_environ_cache(self):
        with patch.dict("os.environ", {"DEBUG": "true"}, clear=True):

            class TestEnviron(Environ):
                DEBUG: bool

            env = TestEnviron()

            with patch.object(env, "_cache") as mock_cache:
                mock_cache.__contains__.return_value = False
                env.DEBUG
                mock_cache.__setitem__.assert_called_once_with("DEBUG", True)

                mock_cache.__contains__.return_value = True
                env.DEBUG
                mock_cache.__getitem__.assert_called_once_with("DEBUG")

    def test_environ_cache_after_os_environ_change(self):
        with patch.dict("os.environ", {"DEBUG": "true"}, clear=True):

            class TestEnviron(Environ):
                DEBUG: bool

            env = TestEnviron()
            self.assertTrue(env.DEBUG)

            os.environ["DEBUG"] = "false"
            self.assertTrue(env.DEBUG)  # Cached value persists

    def test_field_with_default(self):
        with patch.dict("os.environ", {}, clear=True):

            class TestEnviron(Environ):
                DEFAULT_VAR: str = "default"

            env = TestEnviron()
            self.assertEqual(env.DEFAULT_VAR, "default")

            os.environ["DEFAULT_VAR"] = "custom"
            self.assertEqual(env.DEFAULT_VAR, "default")  # Still uses default

    def test_field_conversion_failure(self):
        with patch.dict("os.environ", {"FAIL": "not_an_int"}, clear=True):

            class TestEnviron(Environ):
                FAIL: int = field(lambda x: int(x))

            env = TestEnviron()
            with self.assertRaises(ValueError):
                _ = env.FAIL

    def test_environ_complex_type(self):
        with patch.dict(
            "os.environ", {"DICT": '{"key": "value"}'}, clear=True
        ):

            class TestEnviron(Environ):
                # For testing purposes
                DICT: dict = field(lambda x: eval(x))  # noqa

            env = TestEnviron()
            self.assertEqual(env.DICT, {"key": "value"})

    def test_environ_concurrency(self):
        import threading

        with patch.dict("os.environ", {"SHARED": "value"}, clear=True):

            class TestEnviron(Environ):
                SHARED: str

            env = TestEnviron()

            def access_shared():
                for _ in range(100):
                    _ = env.SHARED

            threads = [
                threading.Thread(target=access_shared) for _ in range(10)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(env.SHARED, "value")
