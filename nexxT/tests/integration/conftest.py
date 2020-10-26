import pytest

def pytest_addoption(parser):
    parser.addoption(
        "--keep-open", action="store_true", default=False, help="keep the gui open after executing the tests."
    )
