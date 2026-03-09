from pathlib import Path

import pytest
from dotenv import load_dotenv


@pytest.fixture(scope="session", autouse=True)
def _load_env() -> None:
    dotenv_path = (
        Path(__file__).parent / "../.env"
    )  # Construct path from current test file dir
    load_dotenv(dotenv_path=dotenv_path)
