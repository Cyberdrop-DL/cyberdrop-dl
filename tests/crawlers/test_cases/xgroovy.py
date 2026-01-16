DOMAIN = "xgroovy"
TEST_CASES = [
    # Video page link
    (
        "https://xgroovy.com/videos/598490/brunette-bombshell-casts-her-magic-in-amateur-pov/",
        [
            {
                "url": "https://xgroovy.com/videos/598490/brunette-bombshell-casts-her-magic-in-amateur-pov",
                "filename": "Brunette Bombshell Casts Her Magic in Amateur POV [598490][1080p].mp4",
                "debrid_link": "ANY",
                "referer": "https://xgroovy.com/videos/598490/brunette-bombshell-casts-her-magic-in-amateur-pov",
                "datetime": 1758692603,
            }
        ],
    ),
    # Gif page link
    (
        "https://xgroovy.com/shemale/gifs/463103/jaw-dropping3",
        [
            {
                "url": "https://xgroovy.com/shemale/gifs/463103/jaw-dropping3",
                "filename": "Jaw-dropping! [463103].mp4",
                "debrid_link": "ANY",
                "referer": "https://xgroovy.com/shemale/gifs/463103/jaw-dropping3",
                "datetime": 1733330169,
            }
        ],
    ),
    # Search
    (
        "https://xgroovy.com/search/helena-price/",
        [
            {
                "url": "re:https://xgroovy.com/videos/",
                "download_folder": r"re:helena\-price \[search\] \(XGroovy\)",
                "referer": "re:https://xgroovy.com/videos/",
                "album_id": None,
            }
        ],
        17,
    ),
    # Pornstars
    (
        "https://xgroovy.com/pornstars/hotangelsfromhell/",
        [
            {
                "url": "ANY",
                "download_folder": r"re:HotAngelsFromHell \[pornstars\] \(XGroovy\)",
                "referer": "re:https://xgroovy.com/videos/",
                "album_id": None,
            }
        ],
        1,
    ),
]
