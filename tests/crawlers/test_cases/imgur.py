DOMAIN = "imgur"
TEST_CASES = [
    {
        "url": "https://imgur.com/gallery/something-wholesome-uvh9Obt",
        "results": [
            {
                "url": "https://i.imgur.com/rKn1KVv.mp4",
                "referer": "https://imgur.com/rKn1KVv",
                "download_folder": "re:Something Wholesome (Imgur)",
                "filename": "rKn1KVv.mp4",
                "original_filename": "rKn1KVv.mp4",
                "album_id": "uvh9Obt",
                "uploaded_at": 1763735344,
            }
        ],
    },
    {
        "url": "https://imgur.com/a/uvh9Obt",
        "results": [
            {
                "url": "https://i.imgur.com/rKn1KVv.mp4",
                "referer": "https://imgur.com/rKn1KVv",
                "download_folder": "re:Something Wholesome (Imgur)",
                "filename": "rKn1KVv.mp4",
                "album_id": "uvh9Obt",
            }
        ],
    },
    {
        "url": "https://imgur.com/rKn1KVv",
        "results": [
            {
                "url": "https://i.imgur.com/rKn1KVv.mp4",
                "referer": "https://imgur.com/rKn1KVv",
                "download_folder": "re:Loose Files (Imgur)",
                "filename": "rKn1KVv.mp4",
                "album_id": None,
            }
        ],
    },
    {
        "url": "https://imgur.com/gallery/broken-egg-by-huleeb-42gHAIK",
        "results": [
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
    },
    {
        "url": "https://imgur.com/download/rKn1KVv",
        "results": [
            {
                "url": "https://i.imgur.com/rKn1KVv.mp4",
                "referer": "https://imgur.com/rKn1KVv",
                "download_folder": "re:Loose Files (Imgur)",
                "filename": "rKn1KVv.mp4",
                "album_id": None,
            }
        ],
    },
]
