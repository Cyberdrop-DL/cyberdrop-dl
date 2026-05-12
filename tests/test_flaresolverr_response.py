from __future__ import annotations

import time

from cyberdrop_dl.clients.flaresolverr import Solution, _parse_cookies
from cyberdrop_dl.clients.response import _FlareSolverrResponse, _infer_content_type_from_body

# ---------------------------------------------------------------------------
# Fixtures: example FlareSolverr JSON responses
# ---------------------------------------------------------------------------

FLARESOLVERR_RESPONSE_EMPTY_HEADERS = {
    "status": "ok",
    "message": "Challenge solved!",
    "solution": {
        "url": "https://1337x.to/cat/Movies/1/",
        "status": 200,
        "cookies": [
            {
                "domain": ".1337x.to",
                "expiry": 1808054295,
                "httpOnly": True,
                "name": "cf_clearance",
                "path": "/",
                "sameSite": "None",
                "secure": True,
                "value": "KKW9gSBPiS8pWkenAaGd82lMQZwcCqSEALdTvs13Tf7QIdxHRN4NKdwhnut21rKA",
            }
        ],
        "userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "headers": {},
        "response": '<html><head>\n<meta charset="utf></html>',
    },
    "startTimestamp": 1776518283422,
    "endTimestamp": 1776518297487,
    "version": "3.4.6",
}

FLARESOLVER_RESP_JSON = {
    "status": "ok",
    "message": "Challenge not detected!",
    "solution": {
        "url": "https://www.tikwm.com/api/user/posts?unique_id=kittyasmr2&count=50&cursor=0",
        "status": 200,
        "response": {
            "code": 0,
            "msg": "success",
            "processed_time": 0.9642,
            "data": {
                "videos": [
                    {
                        "video_id": "7637253304178740500",
                        "region": "CL",
                        "title": "Esa amiga que solo hace videollamada para admirarse 🐥 créditos: jimenita #humor #comedia #Viral #kdramas #paratii ",
                        "content_desc": [
                            "Esa amiga que solo hace videollamada para admirarse 🐥 créditos: jimenita #humor #comedia #Viral #kdramas",
                            "#paratii ",
                        ],
                        "duration": 16,
                    }
                ],
                "cursor": "1745723767416",
                "hasMore": False,
            },
        },
        "headers": {
            "access-control-allow-credentials": "true",
            "access-control-allow-headers": "Content-Type,Content-Length,Accept-Encoding,X-Requested-with, Origin",
            "access-control-allow-methods": "POST,GET,OPTIONS,DELETE",
            "access-control-allow-origin": "*",
            "cf-cache-status": "DYNAMIC",
            "cf-ray": "9f8a6e819968f0-MIA",
            "content-encoding": "br",
            "content-type": "application/json",
            "date": "Fri, 08 May 2026 18:12:17 GMT",
            "nel": '{"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}',
            "server": "cloudflare",
            "x-limit-request-remaining": "9995",
            "x-limit-request-reset": "20864",
        },
        "cookies": [
            {
                "name": "cf_clearance",
                "value": "m5B4ZLfY9b1yGWFI0mQHveDo7Jnb4e",
                "domain": ".tikwm.com",
                "path": "/",
                "expires": 1809798658.438918,
                "size": 417,
                "httpOnly": True,
                "secure": True,
                "session": False,
                "sameSite": "None",
                "priority": "Medium",
                "sameParty": False,
                "sourceScheme": "Secure",
                "sourcePort": 443,
                "partitionKey": "https://tikwm.com",
            }
        ],
        "userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    },
    "startTimestamp": 1778263936203,
    "endTimestamp": 1778263939479,
    "version": "3.3.21",
}


def test_infer_content_type_html() -> None:
    assert _infer_content_type_from_body("<html>test</html>") == "text/html"


def test_infer_content_type_html_with_leading_whitespace() -> None:
    assert _infer_content_type_from_body("  \n <html>") == "text/html"


def test_infer_content_type_json_object() -> None:
    assert _infer_content_type_from_body('{"key": "value"}') == "application/json"


def test_infer_content_type_json_array() -> None:
    assert _infer_content_type_from_body("[1, 2, 3]") == "application/json"


def test_infer_content_type_empty_string() -> None:
    assert _infer_content_type_from_body("") == ""


def test_infer_content_type_only_whitespace() -> None:
    assert _infer_content_type_from_body("   \n\t  ") == ""


def test_parse_cookies_complete_cookie() -> None:
    cookies = [
        {
            "domain": ".example.com",
            "name": "session",
            "path": "/",
            "value": "abc123",
            "secure": True,
            "expires": int(time.time()) + 3600,
        }
    ]
    result = _parse_cookies(cookies)
    assert "session" in result
    assert result["session"].value == "abc123"
    assert result["session"]["domain"] == ".example.com"
    assert result["session"]["secure"] == "TRUE"
    assert int(result["session"]["max-age"]) > 0


def test_parse_cookies_missing_secure_and_expires() -> None:
    """Cookie without 'secure' and 'expires' must not raise KeyError."""
    cookies = [
        {
            "domain": ".example.com",
            "name": "test",
            "path": "/",
            "value": "xyz",
        }
    ]
    result = _parse_cookies(cookies)
    assert "test" in result
    assert result["test"].value == "xyz"
    assert result["test"]["secure"] == ""
    assert result["test"]["max-age"] == ""


def test_parse_cookies_secure_false() -> None:
    cookies = [
        {
            "domain": ".example.com",
            "name": "nosec",
            "path": "/",
            "value": "val",
            "secure": False,
        }
    ]
    result = _parse_cookies(cookies)
    assert result["nosec"]["secure"] == ""


def test_parse_cookies_expired_cookie() -> None:
    """An already-expired cookie should have max-age = 0."""
    cookies = [
        {
            "domain": ".example.com",
            "name": "old",
            "path": "/",
            "value": "stale",
            "expires": 1000000000,
        }
    ]
    result = _parse_cookies(cookies)
    assert result["old"]["max-age"] == "0"


def test_parse_cookies_empty_list() -> None:
    result = _parse_cookies([])
    assert len(result) == 0


# ---------------------------------------------------------------------------
# Solution.from_dict
# ---------------------------------------------------------------------------


def test_solution_from_dict_with_empty_headers() -> None:
    """Parsing the full FlareSolverr solution dict must not raise."""
    solution_data = FLARESOLVERR_RESPONSE_EMPTY_HEADERS["solution"]
    solution = Solution.from_dict(solution_data)
    assert solution.status == 200
    assert str(solution.url) == "https://1337x.to/cat/Movies/1/"
    assert solution.content == '<html><head>\n<meta charset="utf></html>'
    assert len(solution.headers) == 0
    assert "cf_clearance" in solution.cookies


def test_solution_from_dict_cookies_parsed_correctly() -> None:
    solution_data = FLARESOLVERR_RESPONSE_EMPTY_HEADERS["solution"]
    solution = Solution.from_dict(solution_data)
    morsel = solution.cookies["cf_clearance"]
    assert morsel.value == "KKW9gSBPiS8pWkenAaGd82lMQZwcCqSEALdTvs13Tf7QIdxHRN4NKdwhnut21rKA"
    assert morsel["domain"] == ".1337x.to"
    assert morsel["path"] == "/"
    assert morsel["secure"] == "TRUE"


def test_solution_from_dict_json_resp() -> None:
    solution = Solution.from_dict(FLARESOLVER_RESP_JSON["solution"])
    assert type(solution.content) is dict


async def test_flaresolverr_response_infers_html_from_empty_headers() -> None:
    """When FlareSolverr returns empty headers, content-type should be inferred from the body."""
    solution = Solution.from_dict(FLARESOLVERR_RESPONSE_EMPTY_HEADERS["solution"])
    response = _FlareSolverrResponse.create(solution)
    assert response.content_type == "text/html"
    assert response.status == 200
    assert response.location is None


async def test_flaresolverr_response_reads_text() -> None:
    solution = Solution.from_dict(FLARESOLVERR_RESPONSE_EMPTY_HEADERS["solution"])
    response = _FlareSolverrResponse.create(solution)
    text = await response.text()
    assert "<html>" in text


async def test_flaresolverr_response_from_json_resp() -> None:
    solution = Solution.from_dict(FLARESOLVER_RESP_JSON["solution"])
    response = _FlareSolverrResponse.create(solution)
    assert not response._text
    assert response.content_type == "application/json"
    assert response._get_content() == solution.content
    assert await response.json() == solution.content
    assert await response.text() == ""


async def test_flaresolverr_response_with_explicit_content_type() -> None:
    """When headers contain Content-Type, it should be used instead of inference."""
    solution_data = {
        **FLARESOLVERR_RESPONSE_EMPTY_HEADERS["solution"],
        "headers": {"Content-Type": "application/json"},
        "response": '{"data": True}',
    }
    solution = Solution.from_dict(solution_data)
    response = _FlareSolverrResponse.create(solution)
    assert response.content_type == "application/json"


async def test_flaresolverr_response_empty_body_and_empty_headers() -> None:
    """Empty body + empty headers should result in empty content-type string."""
    solution_data = {
        **FLARESOLVERR_RESPONSE_EMPTY_HEADERS["solution"],
        "response": "",
    }
    solution = Solution.from_dict(solution_data)
    response = _FlareSolverrResponse.create(solution)
    assert response.content_type == ""
