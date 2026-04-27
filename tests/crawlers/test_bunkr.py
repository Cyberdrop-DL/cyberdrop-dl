import pytest

from cyberdrop_dl.crawlers import bunkrr


@pytest.mark.parametrize(
    "timestamp, url, expected",
    [
        (
            1774897194,
            "OzE3IjZucGQmazRRF0BTVlh9Njd9d2RteGhobxkKAh0fGxQsNTsrM3IMLCszRxRxQldXIDFuFz01MiIrOCtdVl1DH189aBMnJzg2KGg2aAFdC2lVQn0oM2Y=",
            "https://c2ke.scdn.st/2023-10-31---Giving-Girls-Breast-Examinations-in-Public-o75d8Ygt.mp4",
        )
    ],
)
def test_parse_api_resp(timestamp: int, url: str, expected: str) -> None:
    url = bunkrr._parse_api_resp(url, timestamp, encrypted=True)
    assert url == expected


def test_album_parser() -> None:
    album_js = """
    window.albumFiles = [
        {
            id: 25960373,
            name: "f7e8625e-b50b-42c3-93da-d74bce716c41-md8f1c79417cd16004-zU4LIum1.jpg",
            original: "f7e8625e-b50b-42c3-93da-d74bce716c41-md8f1c79417cd16004.jpg",
            slug: "wWEoCddlaatjj",
            type: "image/jpeg",
            extension: "Image",
            size: 96818,
            timestamp: "10:49:48 27/11/2023",
            thumbnail: "https://static.scdn.st/e2f8a4c6-3d7b-4e19-9a5c-8b1d6f0e3a7c/thumbs/f7e8625e-b50b-42c3-93da-d74bce716c41-md8f1c79417cd16004-zU4LIum1.png",
            cdnEndpoint: "/f7e8625e-b50b-42c3-93da-d74bce716c41-md8f1c79417cd16004-zU4LIum1.jpg"
        },
        {
            id: 25960332,
            name: "c44e4c1a-90d5-4eba-8a58-f71fe3dfaa4f-md4d01c011ab729eda-ZEpjlipI.jpg",
            original: "2023-02-04 - Position 🔞 BONUS.mp4.jpg",
            slug: "tR69eocGrklcG",
            type: "image/jpeg",
            extension: "Image",
            size: 162649,
            timestamp: "10:48:13 27/11/2023",
            thumbnail: "https://static.scdn.st/f4e2d6c8-9b1a-4d3f-8e7c-5a6b2c9d0e1f/thumbs/c44e4c1a-90d5-4eba-8a58-f71fe3dfaa4f-md4d01c011ab729eda-ZEpjlipI.png",
            cdnEndpoint: "/c44e4c1a-90d5-4eba-8a58-f71fe3dfaa4f-md4d01c011ab729eda-ZEpjlipI.jpg"
        },
        {
            id: 25960333,
            name: "caec7e08-8e56-47ac-a4d6-8f2207609ae5-mdb527c6183d37d159-BTEPNkqS.jpg",
            original: "caec7e08-8e56-47ac-a4d6-8f2207609ae5-mdb527c6183d37d159.jpg",
            slug: "irJr4wL1eJBWh",
            type: "image/jpeg",
            extension: "Image",
            size: 110179,
            timestamp: "10:48:13 27/11/2023",
            thumbnail: "https://static.scdn.st/f4e2d6c8-9b1a-4d3f-8e7c-5a6b2c9d0e1f/thumbs/caec7e08-8e56-47ac-a4d6-8f2207609ae5-mdb527c6183d37d159-BTEPNkqS.png",
            cdnEndpoint: "/caec7e08-8e56-47ac-a4d6-8f2207609ae5-mdb527c6183d37d159-BTEPNkqS.jpg"
        },


    ];
    console.log('Album files embedded:', window.albumFiles.length, 'files');
    """
    files = {f.id: f for f in bunkrr._make_album_parser()(album_js)}
    assert len(files) == 3
    file_id = 25960332
    file = files[file_id]
    assert file == bunkrr.File(
        id=file_id,
        name="c44e4c1a-90d5-4eba-8a58-f71fe3dfaa4f-md4d01c011ab729eda-ZEpjlipI.jpg",
        original="2023-02-04 - Position 🔞 BONUS.mp4.jpg",
        slug="tR69eocGrklcG",
        type="image/jpeg",
        extension="Image",
        size=162649,
        timestamp="10:48:13 27/11/2023",
        thumbnail="https://static.scdn.st/f4e2d6c8-9b1a-4d3f-8e7c-5a6b2c9d0e1f/thumbs/c44e4c1a-90d5-4eba-8a58-f71fe3dfaa4f-md4d01c011ab729eda-ZEpjlipI.png",
        cdnEndpoint="/c44e4c1a-90d5-4eba-8a58-f71fe3dfaa4f-md4d01c011ab729eda-ZEpjlipI.jpg",
    )
