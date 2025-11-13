DOMAIN = "tnaflix"
TEST_CASES = [
    # Video
    (
        "https://www.tnaflix.com/amateur-porn/cute-cali_green-big-black-dick-suck/video11464085",
        [
            {
                "url": "re:https://sl190.tnaflix.com/11/46/11464085/cute-cali_green-big-black-dick-suck-240p.mp4",
                "filename": "cute cali_green big black dick suck [11464085][240p].mp4",
                "referer": "https://www.tnaflix.com/amateur-porn/cute-cali_green-big-black-dick-suck/video11464085",
                "datetime": 1722645635,
            }
        ],
    ),
    # Search
    (
        "https://www.tnaflix.com/search?what=spiderbaby",
        [],
        2,
    ),
    (
        "https://www.tnaflix.com/channel/titty-attack",
        [
            {
                "url": "ANY",
                "download_folder": r"re:Titty Attack - \[channel\] \(TNAFlix\)",
            }
        ],
        2,
    ),
]
