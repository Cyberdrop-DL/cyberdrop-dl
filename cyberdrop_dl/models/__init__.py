"""Pydantic models"""

from typing import Any, ClassVar, TypedDict

from cyclopts import Parameter
from pydantic import AnyUrl, BaseModel, Secret, SerializationInfo, model_serializer, model_validator


class AliasModel(BaseModel, populate_by_name=True, defer_build=True): ...


class ConfigGroup(AliasModel):
    def __init_subclass__(cls, *, group: str | None = None, name: str | None = "*") -> None:
        _ = Parameter(group=group or cls.__name__, name=name)(cls)
        return super().__init_subclass__()


class _AppriseURLDict(TypedDict):
    url: str
    tags: set[str]


@Parameter(name="*")
class AppriseURL(AliasModel):
    url: Secret[AnyUrl]
    tags: set[str] = set()

    _OS_SCHEMES: ClassVar[tuple[str, ...]] = "windows", "macosx", "dbus", "qt", "glib", "kde"
    _VALID_TAGS: ClassVar[set[str]] = {"no_logs", "attach_logs", "simplified"}

    def model_post_init(self, *_: Any) -> None:
        if not self.tags.intersection(self._VALID_TAGS):
            self.tags |= {"no_logs"}

        if self.is_os_url:
            self.tags = (self.tags - self._VALID_TAGS) | {"simplified"}

    def __str__(self) -> str:
        return self.format(dump_secret=True)

    @property
    def scheme(self) -> str:
        return self.url.get_secret_value().scheme

    @property
    def is_os_url(self) -> bool:
        return any(scheme in self.scheme for scheme in self._OS_SCHEMES)

    @property
    def attach_logs(self) -> bool:
        return "attach_logs" in self.tags

    @model_serializer()
    def serialize(self, info: SerializationInfo) -> str:
        return self.format(dump_secret=info.mode != "json")

    def format(self, *, dump_secret: bool) -> str:
        url = str(self.url.get_secret_value() if dump_secret else self.url)
        if not self.tags:
            return url
        return f"{','.join(sorted(self.tags))}={url}"

    @model_validator(mode="before")
    @classmethod
    def _validate(cls, obj: object) -> _AppriseURLDict:
        match obj:
            case str():
                return cls._parse_url(obj)

            case dict():
                tags = obj.get("tags") or set()
                url = str(obj.get("url", ""))
                if not tags:
                    return cls._parse_url(url)

                return {"url": url, "tags": tags}

            case _:
                return {"url": str(obj), "tags": set()}

    @staticmethod
    def _parse_url(obj: str) -> _AppriseURLDict:
        match obj.split("://", 1)[0].split("=", 1):
            case [tags_, _scheme]:
                tags = set(tags_.split(","))
                url = obj.split("=", 1)[-1]
            case _:
                tags: set[str] = set()
                url: str = obj

        return {"url": url, "tags": tags}


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


def merge_models[M: BaseModel](default: M, new: M) -> M:
    default_dict = default.model_dump()
    new_dict = new.model_dump(exclude_unset=True)
    updated_dict = merge_dicts(default_dict, new_dict)
    return default.model_validate(updated_dict)
