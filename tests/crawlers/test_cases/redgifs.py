DOMAIN = "redgifs"
TEST_CASES = [
    (
        "https://i.redgifs.com/i/tidyshowybream.jpg",
        [
            {
                "url": "https://media.redgifs.com/TidyShowyBream-large.jpg",
                "filename": "TidyShowyBream-large.jpg",
                "referer": "https://www.redgifs.com/watch/tidyshowybream",
                "album_id": None,
                "uploaded_at": 1734826081,
            }
        ],
    ),
    (
        "https://www.redgifs.com/users/mylovely.ai",
        [
            {
                "url": "ANY",
                "download_folder": "re:mylovely.ai (RedGifs)",
            }
        ],
        range(216, 300),
    ),
]
