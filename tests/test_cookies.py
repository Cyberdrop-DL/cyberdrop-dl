from __future__ import annotations

from http.cookiejar import Cookie, MozillaCookieJar
from http.cookies import SimpleCookie

from cyberdrop_dl.cookies import make_simple_cookie, split_cookies

now = 1_000_000


def make_cookie(
    *,
    domain: str,
    name: str,
    value: str | None,
    secure: bool = True,
    expires: int | None = None,
    path: str = "/",
):
    return Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=True,
        domain_initial_dot=bool(domain.startswith(".")),
        path=path,
        path_specified=bool(path),
        secure=secure,
        # using if explicitly to make it clear.
        expires=expires if expires else None,
        discard=expires == 0,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    )


class TestMakeSimpleCookie:
    def test_normal_cookie(self) -> None:
        cookie = make_cookie(
            name="session",
            value="abc123",
            domain="example.com",
            path="/api",
            secure=True,
            expires=None,
        )
        simple = make_simple_cookie(cookie, now)

        assert isinstance(simple, SimpleCookie)
        morsel = simple["session"]
        assert morsel.value == "abc123"
        assert morsel["domain"] == "example.com"
        assert morsel["path"] == "/api"
        assert morsel["secure"] is True
        assert morsel["max-age"] == ""

    def test_cookie_with_expires(self) -> None:
        cookie = make_cookie(
            name="token",
            value="xyz",
            domain="example.com",
            path="/api",
            secure=False,
            expires=int(now) + 300,
        )
        simple = make_simple_cookie(cookie, now)

        morsel = simple["token"]
        assert morsel.value == "xyz"
        assert morsel["max-age"] == "300"

    def test_cookie_expires_in_the_past(self) -> None:
        cookie = make_cookie(
            name="old",
            value="expired",
            domain="example.com",
            path="/",
            secure=True,
            expires=int(now) - 100,
        )
        simple = make_simple_cookie(cookie, now)
        assert simple["old"]["max-age"] == "0"


def test_split_cookies() -> None:
    cookies = [
        make_cookie(name="session", value="abc123", domain="example.com"),
        make_cookie(name="user", value="user123", domain="www.example.com"),
        make_cookie(name="user", value="user123", domain="example2.com"),
    ]
    cookie_jar = MozillaCookieJar()
    for cookie in cookies:
        cookie_jar.set_cookie(cookie)

    output = split_cookies(cookie_jar)
    assert type(next(iter(output.values()))) is MozillaCookieJar
    assert tuple(output) == ("example.com", "example2.com")
    assert len(output["example.com"]) == 2
    assert len(output["example2.com"]) == 1
