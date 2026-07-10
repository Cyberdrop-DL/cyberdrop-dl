DOMAIN = "wikifeet"
TEST_CASES = [
    {
        "url": "https://pics.wikifeet.com/Fanfan-Feet-7156153.jpg",
        "results": [
            {
                "url": "https://pics.wikifeet.com/Fanfan-Feet-7156153.jpg",
                "filename": "Fanfan-Feet-7156153.jpg",
                "debrid_url": None,
                "original_filename": "Fanfan-Feet-7156153.jpg",
                "referer": "https://pics.wikifeet.com/Fanfan-Feet-7156153.jpg",
                "album_id": None,
                "uploaded_at": None,
                "download_folder": "re:Loose Files (Wikifeet)",
            }
        ],
        "count": 1,
    },
    {
        "url": "https://wikifeet.com/Fanfan3",
        "results": [
            {
                "url": "re:https://pics.wikifeet.com/Fanfan-Feet-",
                "filename": r"re:Fanfan-Feet-(\d+)\.jpg",
                "debrid_url": None,
                "referer": "https://wikifeet.com/Fanfan3",
                "album_id": "Fanfan",
                "uploaded_at": None,
                "download_folder": "re:Fanfan (Wikifeet)",
            },
        ],
        "count": range(299, 330),
    },
]
