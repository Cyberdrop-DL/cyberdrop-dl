DOMAIN = "streamtape.com"
TEST_CASES = [
    # Video
    (
        "https://streamtape.com/v/oelrLvaa3lIJyrR/TnkrBh.mp4",
        [
            {
                "url": "https://streamtape.com/v/oelrLvaa3lIJyrR",
                "filename": "TnkrBh.mp4",
                "referer": "https://streamtape.com/v/oelrLvaa3lIJyrR",
                "datetime": None,
                "debrid_link": "ANY",
            }
        ],
    ),
    # Video Player
    (
        "https://streamtape.com/e/oelrLvaa3lIJyrR",
        [
            {
                "url": "https://streamtape.com/v/oelrLvaa3lIJyrR",
                "filename": "TnkrBh.mp4",
                "referer": "https://streamtape.com/v/oelrLvaa3lIJyrR",
                "debrid_link": "ANY",
                "datetime": None,
            }
        ],
    ),
]
