DOMAIN = "thothub"
TEST_CASES = [
    (
        "https://thothub.to/videos/1415181/kateharperxo/",
        [
            {
                "url": "https://thothub.to/videos/1415181/kateharperxo/",
                "filename": "Kateharperxo [1415181].mp4",
                "referer": "https://thothub.to/videos/1415181/kateharperxo/",
                "album_id": None,
            }
        ],
    ),
    (
        "https://thothub.lol/albums/42921/ivy-king-of-selects/",
        [
            {
                "url": "https://thothub.lol/get_image/45/0fd48eeb530b9232d216b579cd58ce9b/sources/42000/42921/2113169.jpg/",
                "filename": "2113169.jpg",
                "referer": "https://thothub.lol/get_image/45/0fd48eeb530b9232d216b579cd58ce9b/sources/42000/42921/2113169.jpg/",
                "album_id": "42921",
                "datetime": None,
                "download_folder": r"re:Ivy King \- OF Selects \[album\] \(ThotHub\)",
            }
        ],
        112,
    ),
]
