import warnings
from pathlib import Path

from pydantic import BaseModel


class Config(BaseModel):
    path: Path = Path("~/.config")


def test_json_schema() -> None:
    with warnings.catch_warnings(action="error"):
        schema = Config.model_json_schema(mode="validation")
        print(schema)
