DOMAIN = "luxuretv"
TEST_CASES = [
    # Video
    (
        "https://luxuretv.com/videos/tts-372359.html",
        [
            {
                "url": "https://luxuretv.com/videos/tts-372359.html",
                "filename": "tts [372359].mp4",
                "referer": "https://luxuretv.com/videos/tts-372359.html",
                "datetime": 1763236013,
            }
        ],
    ),
    # Search
    (
        "https://luxuretv.com/searchgate/videos/ruby-wren/",
        [
            {
                "url": "ANY",
                "download_folder": r"re:Ruby wren \[search\] \(LuxureTV\)",
            }
        ],
        3,
    ),
]
