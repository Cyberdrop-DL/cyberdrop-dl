DOMAIN = "luscious"
TEST_CASES = [
    {
        "url": "https://members.luscious.net/albums/irl-ass_459630",
        "results": [
            {
                "url": "re:https://cdnio.luscious.net/Crucifery/459630/",
                "debrid_url": None,
                "referer": "re:https://members.luscious.net/pictures/album/irl-ass_459630/id/",
                "album_id": "459630",
                "uploaded_at": int,
                "download_folder": "re:IRL Ass (Luscious)",
            },
        ],
        "count": 66,
    },
    {
        "url": "https://www.luscious.net/albums/list?album_type=manga&tagged=%2Bcharacter:_bianca&page=1",
        "results": [
            {
                "url": "ANY",
                "download_folder": "re:+character-_bianca [search]/",
            },
        ],
        "count": range(1289, 1500),
    },
    {
        "url": "https://www.luscious.net/albums/list?album_type=manga&tagged=%2Bcharacter:_bianca&page=2",
        "results": [],
        "count": range(306, 400),
    },
]
