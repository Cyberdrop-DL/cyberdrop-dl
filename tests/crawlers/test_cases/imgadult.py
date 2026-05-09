DOMAIN = "imgadult.com"
TEST_CASES = [
    {
        "url": "https://imgadult.com/img-685761cc22595.html",
        "results": [
            {
                "url": "https://imgadult.com/upload/big/2025/06/22/685761cc22593.jpg",
                "filename": "1092.jpg",
                "original_filename": "685761cc22593.jpg",
                "referer": "https://imgadult.com/img-685761cc22595.html",
                "album_id": None,
                "uploaded_at": None,
            }
        ],
    },
    {
        "url": "https://imgadult.com/upload/big/2025/06/22/685761cc22593.jpg",
        "description": "IDs of thumbnails and src images are different. CDL should fail",
        "results": [],
    },
]
