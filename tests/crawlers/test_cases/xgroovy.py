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
    # Image
    (
        "https://xgroovy.com/photos/1082475/hope-you-like-them-perky-and-natural/",
        [
            {
                "url": "https://photos.xgroovy.com/contents/albums/sources/1082000/1082475/1496153.jpg",
                "download_folder": r"re:Hope you like them perky and natural \(XGroovy\)",
                "referer": "https://xgroovy.com/photos/1082475/hope-you-like-them-perky-and-natural",
                "filename": "1496153.jpg",
                "album_id": "1082475",
            }
        ],
    ),
    # Album
    (
        "https://xgroovy.com/photos/1081573/without-piercing-this-view-is-more-appetizing/",
        [
            {
                "url": "re:https://photos.xgroovy.com/contents/albums/sources/1081000/1081573/",
                "download_folder": r"re:Without piercing, this view is more appetizing \(XGroovy\)",
                "referer": "re:https://xgroovy.com/photos/1081573/without-piercing-this-view-is-more-appetizing",
                "album_id": "1081573",
            },
        ],
        12,
    ),
    # Direct File
    (
        "https://photos.xgroovy.com/contents/albums/sources/1081000/1081200/1493360.jpg",
        [
            {
                "url": "https://photos.xgroovy.com/contents/albums/sources/1081000/1081200/1493360.jpg",
                "download_folder": r"re:Loose Files \(XGroovy\)",
                "referer": "https://photos.xgroovy.com/contents/albums/sources/1081000/1081200/1493360.jpg",
                "filename": "1493360.jpg",
            }
        ],
    ),
]
