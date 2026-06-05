import pytest
import yarl

from cyberdrop_dl.models import AppriseURL


@pytest.mark.parametrize(
    ("value", "expected_url", "expected_tags"),
    [
        (
            "ses://user@domain/AccessKeyID/AccessSecretKey/",
            "ses://user@domain/AccessKeyID/AccessSecretKey/",
            {"no_logs"},
        ),
        (
            "updated=bluesky://Handle:1234/TargetHandle1/TargetHandle2/",
            "bluesky://Handle:1234/TargetHandle1/TargetHandle2/",
            {"no_logs", "updated"},
        ),
        (
            "attach_logs,updated=tgram://bottoken/ChatID1/ChatID2/ChatIDN",
            "tgram://bottoken/ChatID1/ChatID2/ChatIDN",
            {"attach_logs", "updated"},
        ),
        (
            {
                "url": "attach_logs,updated=tgram://bottoken/ChatID1/ChatID2/ChatIDN",
            },
            "tgram://bottoken/ChatID1/ChatID2/ChatIDN",
            {"attach_logs", "updated"},
        ),
        (
            {
                "url": "tgram://bottoken/ChatID1/ChatID2/ChatIDN",
                "tags": {"attach_logs", "updated", "another_tag"},
            },
            "tgram://bottoken/ChatID1/ChatID2/ChatIDN",
            {"attach_logs", "updated", "another_tag"},
        ),
        (
            yarl.URL("discord://webhook_id/webhook_token"),
            "discord://webhook_id/webhook_token",
            {"no_logs"},
        ),
    ],
)
def test_apprise_url_model(value: object, expected_url: str, expected_tags: set[str]) -> None:
    result = AppriseURL.model_validate(value)
    assert str(result.url.get_secret_value()) == expected_url
    assert result.tags.intersection(AppriseURL._VALID_TAGS)
    assert result.tags == expected_tags
