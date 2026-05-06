DOMAIN = "imagepond.net"
TEST_CASES = [
    (
        "https://www.imagepond.net/image/zJfHAH",
        [
            {
                "url": "https://media.imagepond.net/media/Palm-Desert-Resuscitation-Education-YourCPRMD.com8c5d221f74fbb880.png",
                "referer": "https://www.imagepond.net/i/chv_866552",
                "download_folder": "re:Loose Files (ImagePond)",
                "filename": "Palm Desert Resuscitation Education (YourCPRMD.com).png",
                "album_id": None,
                "uploaded_at": 1759122000,
            },
        ],
    ),
    (
        "https://www.imagepond.net/image/zJfHAH",
        [
            {
                "url": "https://media.imagepond.net/media/Palm-Desert-Resuscitation-Education-YourCPRMD.com8c5d221f74fbb880.png",
                "referer": "https://www.imagepond.net/i/chv_866552",
            },
        ],
    ),
    (
        "https://www.imagepond.net/image/zJfHAH/download",
        [
            {
                "url": "https://media.imagepond.net/media/Palm-Desert-Resuscitation-Education-YourCPRMD.com8c5d221f74fbb880.png",
                "referer": "https://www.imagepond.net/i/chv_866552",
            },
        ],
    ),
    (
        "https://media.imagepond.net/media/Palm-Desert-Resuscitation-Education-YourCPRMD.com8c5d221f74fbb880.png",
        [
            {
                "url": "https://media.imagepond.net/media/Palm-Desert-Resuscitation-Education-YourCPRMD.com8c5d221f74fbb880.png",
                "referer": "https://media.imagepond.net/media/Palm-Desert-Resuscitation-Education-YourCPRMD.com8c5d221f74fbb880.png",
                "download_folder": "re:Loose Files (ImagePond)",
                "filename": "Palm-Desert-Resuscitation-Education-YourCPRMD.com8c5d221f74fbb880.png",
                "album_id": None,
                "uploaded_at": None,
            },
        ],
    ),
    (
        "https://www.imagepond.net/i/3RxARn4j",
        [
            {
                "url": "https://media.imagepond.net/media/videos/VID_20260404_071357_214_a9cdyOhE.mp4",
                "domain": "imagepond.net",
                "referer": "https://www.imagepond.net/i/3RxARn4j",
                "filename": "VID_20260404_071357_214.mp4",
                "uploaded_at": 1775278800,
            }
        ],
    ),
    (
        "https://www.imagepond.net/i/9TVLS36c/download/file",
        [
            {
                "url": "https://media.imagepond.net/media/archives/Images_kM5dpzpw.zip",
                "referer": "https://www.imagepond.net/i/9TVLS36c",
                "filename": "Images.zip",
            }
        ],
    ),
    (
        "https://www.imagepond.net/a/AY75C28f",
        [
            {
                "url": "re:https://media.imagepond.net/media/",
                "referer": "re:https://www.imagepond.net/i/",
                "album_id": "AY75C28f",
                "download_folder": "re:vic (ImagePond)",
            }
        ],
        21,
    ),
]
