DOMAIN = "streamtape.com"
TEST_CASES = [
    # Video
    (
        "https://streamtape.com/v/oelrLvaa3lIJyrR/TnkrBh.mp4",
        [
            {
                "url": r"re:https://\d+\.tapecontent.net/radosgw/oelrLvaa3lIJyrR/.*?/TnkrBh\.mp4",
                "filename": "TnkrBh.mp4",
                "referer": "https://streamtape.com/v/oelrLvaa3lIJyrR",
                "datetime": None,
            }
        ],
    ),
    # Video Player
    (
        "https://streamtape.com/e/oelrLvaa3lIJyrR",
        [
            {
                "url": r"re:https://\d+\.tapecontent.net/radosgw/oelrLvaa3lIJyrR/.*?/TnkrBh\.mp4",
                "filename": "TnkrBh.mp4",
                "referer": "https://streamtape.com/v/oelrLvaa3lIJyrR",
                "datetime": None,
            }
        ],
    ),
]
