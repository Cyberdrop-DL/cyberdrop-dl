from pydantic import dataclasses

from cyberdrop_dl.crawlers.twitter.models import Status


@dataclasses.dataclass(slots=True)
class StatusResponse:
    code: int
    status: Status
