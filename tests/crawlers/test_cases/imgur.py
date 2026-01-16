DOMAIN = "imgur"
TEST_CASES = [
    (
        "https://imgur.com/gallery/something-wholesome-uvh9Obt",
        [
            {
                "url": "https://i.imgur.com/rKn1KVv.mp4",
                "referer": "https://imgur.com/rKn1KVv",
                "download_folder": "re:Something Wholesome (Imgur)",
                "filename": "rKn1KVv.mp4",
                "original_filename": "rKn1KVv.mp4",
                "album_id": "uvh9Obt",
                "datetime": 1763735344,
            }
        ],
    ),
    (
        "https://imgur.com/a/uvh9Obt",
        [
            {
                "url": "https://i.imgur.com/rKn1KVv.mp4",
                "referer": "https://imgur.com/rKn1KVv",
                "download_folder": "re:Something Wholesome (Imgur)",
                "filename": "rKn1KVv.mp4",
                "album_id": "uvh9Obt",
            }
        ],
    ),
    (
        "https://imgur.com/rKn1KVv",
        [
            {
                "url": "https://i.imgur.com/rKn1KVv.mp4",
                "referer": "https://imgur.com/rKn1KVv",
                "download_folder": "re:Loose Files (Imgur)",
                "filename": "rKn1KVv.mp4",
                "album_id": None,
            }
        ],
    ),
    (
        "https://imgur.com/gallery/broken-egg-by-huleeb-42gHAIK",
        [
            {
                "url": "https://i.imgur.com/moPWbvA.jpeg",
                "referer": "https://imgur.com/moPWbvA",
                "download_folder": "re:broken egg, by huleeb (Imgur)",
                "filename": "moPWbvA.jpeg",
                "album_id": "42gHAIK",
            },
            {"url": "https://i.imgur.com/OlaWu7S.jpeg"},
            {"url": "https://i.imgur.com/KVGXtsa.jpeg"},
            {"url": "https://i.imgur.com/7Em9NEr.jpeg"},
        ],
    ),
]
