from typing import Any

from cyberdrop_dl.utils.traversal import traverse


def test_traverse() -> None:
    data = {
        "a": 1,
        "b": "2",
        "c": 3,
        "d": ["", 2],
    }
    result = list(traverse(data, lambda _, value: isinstance(value, int)))

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

    result = list(traverse(data, lambda _, value: isinstance(value, int)))

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
                }
            ]
        },
    ]

    result = list(traverse(data, lambda _, value: isinstance(value, int)))

    assert result == [
        ((0,), 1),
        ((1, 0), 2),
        ((1, 1, 0), 3),
        ((1, 1, 3), 4),
        ((1, 1, 5), 5),
        ((2,), 6),
        ((3, "users", 0, "id"), 1),
    ]

    result = list(traverse(data, lambda _, value: value and type(value) is dict))
    assert result == [
        (
            (3,),
            {
                "users": [
                    {"id": 1, "name": "john"},
                ]
            },
        ),
    ]
    result = list(traverse(data, lambda _, value: type(value) is dict and value.get("name")))
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

    result = list(traverse(data, lambda _, value: isinstance(value, dict)))
    assert result == [((), data)]


def test_no_matches() -> None:
    data = {"a": [1, 2], "b": 3}

    result = list(traverse(data, lambda _, value: isinstance(value, tuple)))

    assert result == []


def test_root_value_matches() -> None:
    value = 42

    result = list(traverse(value, lambda _, item: item == 42))
    assert result == [((), 42)]


def test_root_path_is_preserved() -> None:
    data = {"a": 1}

    result = list(
        traverse(
            data,
            lambda _, value: isinstance(value, int),
            path=("root", 10),
        )
    )

    assert result == [(("root", 10, "a"), 1)]


def test_empty_containers() -> None:
    data = {"a": [], "b": {}, "c": ()}
    result = list(traverse(data, lambda *_: False))
    assert result == []


def test_empty_container_can_match() -> None:
    data = {"a": [], "b": {}}
    result = list(traverse(data, lambda _, value: isinstance(value, (list, dict))))
    assert result == [((), data)]
    result = list(traverse(data, lambda _, value: isinstance(value, list)))
    assert result == [(("a",), [])]


def test_preserves_dictionary_insertion_order():
    data = {"z": 1, "a": 2, "m": 3}

    result = list(traverse(data, lambda _, value: isinstance(value, int)))

    assert result == [
        (("z",), 1),
        (("a",), 2),
        (("m",), 3),
    ]


def test_visits_values_not_dictionary_keys() -> None:
    data = {1: "one", 2: "two"}
    result = list(traverse(data, lambda _, value: isinstance(value, int)))
    assert result == []


def test_visitor_receives_path_and_value() -> None:
    calls = []
    data = {"a": [10]}

    def visitor(path: Any, value: Any):
        calls.append((path, value))
        return False

    list(traverse(data, visitor))

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
    result = list(traverse(data, lambda _, value: type(value) is dict and value.get("a") == "target"))
    assert result
    path, value = result[0]
    assert path == ("my_key", "another_key", 1)
    assert value == inner_data
    assert value is inner_data
    assert data == sample
