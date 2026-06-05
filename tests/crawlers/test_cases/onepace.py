DOMAIN = "onepace.net"
TEST_CASES = [
    {
        "url": "https://onepace.net/en/watch",
        "results": [
            {
                "url": "re:https://pixeldrain.com/api/file/",
                "debrid_link": None,
                "referer": "re:https://pixeldrain.com/u",
                "album_id": str,
                "uploaded_at": int,
                "download_folder": r"re:OnePace\/.*\(PixelDrain\)$",
            },
        ],
        "count": range(470, 500),
    }
]
