DOMAIN = "erome"
TEST_CASES = [
    {
        "url": "https://www.erome.com/a/JSXnUS4Y",
        "results": [
            {
                "url": "re:https://s51.erome.com/3982/JSXnUS4Y/TMXwTHuO.jpeg",
                "filename": "TMXwTHuO.jpeg",
                "debrid_url": None,
                "original_filename": "TMXwTHuO.jpeg",
                "referer": "https://www.erome.com/a/JSXnUS4Y",
                "album_id": "JSXnUS4Y",
                "uploaded_at": None,
                "download_folder": "re:who likes abs- (Erome)",
                "thumbnail": None,
                "size": None,
                "duration": None,
                "parents": [],
                "metadata": {},
                "extra_info": {},
                "id": ["erome", "/3982/JSXnUS4Y/TMXwTHuO.jpeg"],
            },
            {
                "url": "re:https://s51.erome.com/3982/JSXnUS4Y/KtkQrRqf.jpeg",
                "filename": "KtkQrRqf.jpeg",
            },
        ],
    },
    {
        "url": "https://erome.com/a/JSXnUS4Y",
        "description": "URL must be resolved to www.erome.com to pass CORS",
        "results": [
            {
                "url": "re:https://s51.erome.com/3982/JSXnUS4Y/TMXwTHuO.jpeg",
                "filename": "TMXwTHuO.jpeg",
                "referer": "https://www.erome.com/a/JSXnUS4Y",
                "download_folder": "re:who likes abs- (Erome)",
                "album_id": "JSXnUS4Y",
                "uploaded_at": None,
            },
            {"url": "re:https://s51.erome.com/3982/JSXnUS4Y/KtkQrRqf.jpeg", "filename": "KtkQrRqf.jpeg"},
        ],
    },
    {
        "url": "https://www.erome.com/a/osUNHQvy",
        "results": [
            {
                "url": "https://v19.erome.com/4075/osUNHQvy/wZcJpWWD_720p.mp4",
                "filename": "wZcJpWWD_720p.mp4",
                "referer": "https://www.erome.com/a/osUNHQvy",
                "download_folder": "re:perfect gym outfit (Erome)",
                "album_id": "osUNHQvy",
                "uploaded_at": None,
            }
        ],
    },
]
