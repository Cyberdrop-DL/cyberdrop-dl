DOMAIN = "anysex"
TEST_CASES = [
    # Video page link
    (
        "https://anysex.com/video/475758/2-sexy-latina-fitness-girls-get-dicked-hard-by-2-beefy-dudes-outdoor-indoor/",
        [
            {
                "url": "https://anysex.com/video/475758/2-sexy-latina-fitness-girls-get-dicked-hard-by-2-beefy-dudes-outdoor-indoor",
                "filename": "2 Sexy Latina Fitness-girls Get Dicked Hard By 2 Beefy Dudes Outdoor  Indoo [475758][1080p].mp4",
                "debrid_link": "ANY",
                "referer": "https://anysex.com/video/475758/2-sexy-latina-fitness-girls-get-dicked-hard-by-2-beefy-dudes-outdoor-indoor",
                "datetime": 1761678940,
            }
        ],
    ),
    # Video with unknown resolution
    (
        "https://anysex.com/video/89167/amazing-blond-slut-makes-a-horny-dude-to-suck-the-dick-of-the-other-stud/",
        [
            {
                "url": "https://anysex.com/video/89167/amazing-blond-slut-makes-a-horny-dude-to-suck-the-dick-of-the-other-stud",
                "filename": "Amazing blond slut makes a horny dude to suck the dick of the other stud [89167].mp4",
                "debrid_link": "ANY",
                "referer": "https://anysex.com/video/89167/amazing-blond-slut-makes-a-horny-dude-to-suck-the-dick-of-the-other-stud",
                "datetime": 1381968000,
            }
        ],
    ),
    # Album page link
    (
        "https://anysex.com/photos/156337/only-5-0-but-thick-and-curvy-in-all-the-right-places/",
        [
            {
                "url": "re:https://photos.anysex.com/contents/albums/main/1920x9999/156000",
                "download_folder": r"re:Only 50 but thick and curvy in all the right places! \[album\] \(AnySex\)",
                "referer": "re:https://photos.anysex.com/contents/albums/main/1920x9999/156000",
                "album_id": "156337",
            }
        ],
        8,
    ),
    # Album with just one image
    (
        "https://anysex.com/shemale/photos/156591/natures-big-secret/",
        [
            {
                "url": "https://photos.anysex.com/contents/albums/main/1920x9999/156000/156591/255953.jpg",
                "download_folder": r"re:Natures big secret ️ \[album\] \(AnySex\)",
                "referer": "https://photos.anysex.com/contents/albums/main/1920x9999/156000/156591/255953.jpg",
                "album_id": "156591",
            }
        ],
        1,
    ),
    # Search
    (
        "https://anysex.com/search/?q=helena-price",
        [
            {
                "url": "ANY",
                "download_folder": r"re:helena price [search] (AnySex)",
                "referer": "ANY",
                "album_id": None,
            }
        ],
        range(18, 30),
    ),
]
