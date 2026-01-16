import pytest
from bs4 import BeautifulSoup

from cyberdrop_dl import ddos_guard
from cyberdrop_dl.exceptions import DDOSGuardError

anubis_html = """
    <!doctype html>
    <html lang="en">
    <head>
        <title>Making sure you&#39;re not a bot!</title>
        <script id="anubis_version" type="application/json">"v1.23.0"</script><script id="anubis_challenge" type="application/json">{"rules":{"algorithm":"fast","difficulty":5,"report_as":5},"challenge":{"id":"019abb13-2859-7587-bec3-16e0a3f67ce9","method":"fast","randomData":"1b7a4c4a35a9e11ac23c2ae78845476ed627d1f36c8c27c1b3386d7c6f997c2f803fbfd3884b9b51642859e02537a62b9032b8b58b38d4af400aa62c8293ba85","issuedAt":"2025-11-25T12:53:06.265369852Z","metadata":{"User-Agent":"Mozilla/5.0 (X11; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0","X-Real-Ip":""},"spent":false}}</script><script id="anubis_base_prefix" type="application/json">""</script><script id="anubis_public_url" type="application/json">""</script>
    </head>
    <body id="top">
        <main>
            <h1 id="title" class="centered-div">Making sure you&#39;re not a bot!</h1>
            <div class="centered-div">
                <img id="image" style="width:100%;max-width:256px;" src="/.within.website/x/cmd/anubis/static/img/pensive.webp?cacheBuster=v1.23.0"> <img style="display:none;" style="width:100%;max-width:256px;" src="/.within.website/x/cmd/anubis/static/img/happy.webp?cacheBuster=v1.23.0">
                <p id="status">Loading...</p>
                <script async type="module" src="/.within.website/x/cmd/anubis/static/js/main.mjs?cacheBuster=v1.23.0"></script>
                <div id="progress" role="progressbar" aria-labelledby="status">
                <div class="bar-inner"></div>
                </div>
                <details>
                <p>You are seeing this because the administrator of this website has set up Anubis to protect the server against the scourge of AI companies aggressively scraping websites. This can and does cause downtime for the websites, which makes their resources inaccessible for everyone.</p>
                </details>
            </footer>
        </main>
    </body>
    </html>
"""
anubis_soup = BeautifulSoup(anubis_html, "html.parser")


def test_anubis_detection() -> None:
    assert ddos_guard.Anubis.check(anubis_soup)


def test_anubis_parse_challenge() -> None:
    anubis = ddos_guard.Anubis.parse_challenge(anubis_soup)
    assert anubis
    assert anubis == ddos_guard._AnubisChallenge(
        id="019abb13-2859-7587-bec3-16e0a3f67ce9",
        data="1b7a4c4a35a9e11ac23c2ae78845476ed627d1f36c8c27c1b3386d7c6f997c2f803fbfd3884b9b51642859e02537a62b9032b8b58b38d4af400aa62c8293ba85",
        difficulty=5,
    )


async def test_solve_anubis_challenge() -> None:
    challenge = ddos_guard.Anubis.parse_challenge(anubis_soup)
    assert challenge
    solution = await ddos_guard.Anubis.solve(challenge)
    assert solution == ddos_guard._AnubisSolution(
        id="019abb13-2859-7587-bec3-16e0a3f67ce9",
        nonce=1676094,
        hash="00000e426afc08534b13bb3f75bad02dc20d73d70674b9dc174416cc7d3685e6",
        workers=2,
        difficulty=5,
        total_time=0,
    )


async def test_ddos_response_should_raise_ddos_guard_error() -> None:
    with pytest.raises(DDOSGuardError):
        await ddos_guard.check(anubis_html)
