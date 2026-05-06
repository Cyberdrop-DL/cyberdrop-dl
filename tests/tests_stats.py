import pytest

from cyberdrop_dl import stats
from cyberdrop_dl.progress.scraping.errors import UIError


@pytest.mark.parametrize(
    "scrape_errors, download_errors, expected_msgs",
    [
        (
            ["Client Connector SSL Error", "502 Bad Gateway"],
            ["1234 Bad Gateway"],
            [
                "------------------------------",
                "Scrape Errors:",
                "       Client Connector SSL Error: 0",
                "   502 Bad Gateway: 0",
                "------------------------------",
                "Download Errors:",
                "  1234 Bad Gateway: 0",
            ],
        ),
        (
            ["Error1", "Error2"],
            ["Error3", "Error4"],
            [
                "------------------------------",
                "Scrape Errors:",
                "  Error1: 0",
                "  Error2: 0",
                "------------------------------",
                "Download Errors:",
                "  Error3: 0",
                "  Error4: 0",
            ],
        ),
        (
            ["Error1", "Error2"],
            ["Error3", "2 Error4", "Error5"],
            [
                "------------------------------",
                "Scrape Errors:",
                "    Error1: 0",
                "    Error2: 0",
                "------------------------------",
                "Download Errors:",
                "    Error3: 0",
                "  2 Error4: 0",
                "    Error5: 0",
            ],
        ),
    ],
)
def test_stats_formating(
    logs: pytest.LogCaptureFixture,
    scrape_errors: tuple[str, ...],
    download_errors: tuple[str, ...],
    expected_msgs: list[str],
) -> None:

    stats.print_errors(
        tuple(UIError.parse(msg, count=0) for msg in scrape_errors),
        tuple(UIError.parse(msg, count=0) for msg in download_errors),
    )
    assert logs.messages == expected_msgs
