"""Pydantic models"""

from typing import ClassVar, TypedDict

from cyclopts import Parameter
from pydantic import AnyUrl, BaseModel, Secret, SerializationInfo, model_serializer, model_validator


def get_model_fields(model: BaseModel, *, exclude_unset: bool = True) -> set[str]:
    fields = set()
    for submodel_name, submodel in model.model_dump(exclude_unset=exclude_unset).items():
        for field_name in submodel:
            fields.add(f"{submodel_name}.{field_name}")

    return fields


class AliasModel(BaseModel, populate_by_name=True, defer_build=True): ...


class SettingsGroup(AliasModel):
    def __init_subclass__(cls, group: str | None = None) -> None:
        _ = Parameter(group=group or cls.__name__, name="*")(cls)
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

    def model_post_init(self, *_) -> None:
        if not self.tags.intersection(self._VALID_TAGS):
            self.tags = self.tags | {"no_logs"}

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

    def format(self, dump_secret: bool) -> str:
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
