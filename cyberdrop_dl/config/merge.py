from typing import Any, TypeVar

from pydantic import BaseModel


def add_or_remove_lists(cli_values: list[str], config_values: list[str]) -> None:
    exclude = {"+", "-"}
    if cli_values:
        if cli_values[0] == "+":
            new_values_set = set(config_values + cli_values)
            cli_values.clear()
            cli_values.extend(sorted(new_values_set - exclude))
        elif cli_values[0] == "-":
            new_values_set = set(config_values) - set(cli_values)
            cli_values.clear()
            cli_values.extend(sorted(new_values_set - exclude))


def merge_dicts(dict1: dict[str, Any], dict2: dict[str, Any]) -> dict[str, Any]:
    for key, val in dict1.items():
        if isinstance(val, dict):
            if key in dict2 and isinstance(dict2[key], dict):
                merge_dicts(val, dict2[key])
        elif key in dict2:
            dict1[key] = dict2[key]

    for key, val in dict2.items():
        if key not in dict1:
            dict1[key] = val

    return dict1


M = TypeVar("M", bound=BaseModel)


def merge_models(default: M, new: M) -> M:
    default_dict = default.model_dump()
    new_dict = new.model_dump(exclude_unset=True)

    updated_dict = merge_dicts(default_dict, new_dict)
    return default.model_validate(updated_dict)
