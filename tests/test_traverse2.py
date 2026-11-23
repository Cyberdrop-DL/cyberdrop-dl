from typing import Any

import pytest

from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils.traversal2 import Visitor, traverse


def test_docstring_example() -> None:
    obj = [{}, 12345, {"key": "john"}]
    assert traverse(obj, 2, "key").value() == "john"
    assert traverse(obj, ..., "key").value() == "john"

    with pytest.raises(ScrapeError):
        traverse(obj, ..., {"key": {int}}).value()

    assert traverse(obj, ..., {"key": {int}}).get_value() is None


def test_traverse() -> None:
    data = {
        "a": 1,
        "b": "2",
        "c": 3,
        "d": ["", 2],
    }
    result = list(traverse(data, ..., {int}))

    assert result == [
        (("a",), 1),
        (("c",), 3),
        (("d", 1), 2),
    ]


def test_nested_dicts() -> None:
    data = {
        "a": {
            "b": 1,
            "c": "2",
            "d": 3,
        },
        "e": 4,
    }

    result = list(traverse(data, ..., {int}))

    assert result == [
        (("a", "b"), 1),
        (("a", "d"), 3),
        (("e",), 4),
    ]


def test_mixed_nested_structures() -> None:
    data = [
        1,
        (
            2,
            [3, "text", {}, 4, {}, 5],
        ),
        6,
        {
            "users": [
                {
                    "id": 1,
                    "name": "john",
                },
                {},
            ]
        },
    ]

    result = list(traverse(data, ..., {int}))

    assert result == [
        ((0,), 1),
        ((1, 0), 2),
        ((1, 1, 0), 3),
        ((1, 1, 3), 4),
        ((1, 1, 5), 5),
        ((2,), 6),
        ((3, "users", 0, "id"), 1),
    ]

    result = list(traverse(data, ..., (filter, {dict})))
    assert result == [
        (
            (3,),
            {
                "users": [
                    {"id": 1, "name": "john"},
                    {},
                ]
            },
        ),
    ]

    result = list(traverse(data, ..., {"name": {str}}))
    assert result == [
        (
            (3, "users", 0),
            {"id": 1, "name": "john"},
        )
    ]


def test_matching_parent_stops_recursion() -> None:
    data = {
        "a": {
            "b": 1,
        },
        "c": 2,
    }

    result = list(traverse(data, (filter, {dict})))
    assert result == [((), data)]
    result = list(traverse(data, ..., (filter, {dict})))
    assert result == [(("a",), {"b": 1})]


def test_no_matches() -> None:
    data = {"a": [1, 2], "b": 3}

    result = list(traverse(data, ..., {tuple}))

    assert result == []


def test_root_value_matches() -> None:
    value = 42

    result = list(traverse(value, lambda item: item == 42))
    assert result == [((), 42)]
    assert list(traverse(value, ..., lambda item: item == 42)) == []


def test_empty_containers() -> None:
    data = {"a": [], "b": {}, "c": (2,), "d": ()}
    result = list(traverse(data, filter))
    assert result == [((), data)]
    result = list(traverse(data, ..., filter))
    assert result == [(("c",), (2,))]


def test_empty_container_can_match() -> None:
    data = {"a": [], "b": {}}
    result = list(traverse(data, {(list, dict)}))
    assert result == [((), data)]
    result = list(traverse(data, ..., {(list, dict)}))
    assert result == [(("a",), []), (("b",), {})]
    result = list(traverse(data, ..., {list}))
    assert result == [(("a",), [])]


def test_preserves_dictionary_insertion_order() -> None:
    data = {"z": 1, "a": 2, "m": 3}

    result = list(traverse(data, ..., {int}))

    assert result == [
        (("z",), 1),
        (("a",), 2),
        (("m",), 3),
    ]

    result = list(traverse(data, {"a": lambda x: x == 2}))
    assert result == [((), data)]
    assert result[0][1] == data
    assert result[0][1] is not data
    assert tuple(result[0][1]) == tuple(data)


def test_visits_values_not_dictionary_keys() -> None:
    data = {1: "one", 2: "two"}
    result = list(traverse(data, ..., {int}))
    assert result == []


def test_visitor_receives_path_and_value() -> None:
    calls = []
    data = {"a": [10]}

    def visitor(path: Any, value: Any):
        calls.append((path, value))
        return False, value

    list(traverse(data, Visitor(visitor)))
    list(traverse(data, ..., Visitor(visitor)))

    assert calls == [
        ((), {"a": [10]}),
        (("a",), [10]),
        (("a", 0), 10),
    ]


def test_does_not_mutate_traversed_objects() -> None:
    from copy import deepcopy

    inner_data = {"a": "target", "b": -1, 3: [123, 321]}
    data = {1: "one", "my_key": {"another_key": [42, inner_data]}}
    sample = deepcopy(data)
    result = list(traverse(data, ..., {"a": {"target"}}))
    assert result
    path, value = result[0]
    assert path == ("my_key", "another_key", 1)
    assert value == inner_data
    assert value is not inner_data
    assert data == sample
