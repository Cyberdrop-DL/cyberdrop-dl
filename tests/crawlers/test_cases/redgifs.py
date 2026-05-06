DOMAIN = "redgifs"
TEST_CASES = [
    {
        "url": "https://i.redgifs.com/i/tidyshowybream.jpg",
        "results": [
            {
                "url": "https://media.redgifs.com/TidyShowyBream-large.jpg",
                "filename": "TidyShowyBream-large.jpg",
                "referer": "https://www.redgifs.com/watch/tidyshowybream",
                "album_id": None,
                "uploaded_at": 1734826081,
            }
        ],
    },
    {
        "url": "https://www.redgifs.com/users/mylovely.ai",
        "results": [{"url": "ANY", "download_folder": "re:mylovely.ai (RedGifs)"}],
        "count": range(216, 300),
    },
]
