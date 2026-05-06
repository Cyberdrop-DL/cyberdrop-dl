DOMAIN = "toonily"
TEST_CASES = [
    (
        "https://toonily.com/serie/black-crow/",
        [
            {
                "url": "https://data.tnlycdn.com/chapters/manga_66d8f7bfa8ed9/03ae6f538b989573c121b28f7af4f38a/01.jpg",
                "filename": "01.jpg",
                "referer": "https://toonily.com/serie/black-crow-6780cc7a/chapter-1",
                "album_id": None,
                "uploaded_at": 1725498328,
                "download_folder": r"re:Black Crow (Toonily)/Chapter 1",
            }
        ],
        1634,
    ),
    (
        "https://toonily.com/serie/black-crow-6780cc7a/chapter-1/",
        [
            {
                "url": "https://data.tnlycdn.com/chapters/manga_66d8f7bfa8ed9/03ae6f538b989573c121b28f7af4f38a/01.jpg",
                "filename": "01.jpg",
                "referer": "https://toonily.com/serie/black-crow-6780cc7a/chapter-1",
                "album_id": None,
                "uploaded_at": 1725498328,
                "download_folder": r"re:Black Crow (Toonily)/Chapter 1",
            }
        ],
        50,
    ),
    (
        "https://toonily.com/serie/glorious-homecoming-440a49b5/chapter-6/",
        [
            {
                "url": "ANY",
                "referer": "https://toonily.com/serie/glorious-homecoming-440a49b5/chapter-6",
                "album_id": None,
                "download_folder": r"re:Glorious Homecoming (Toonily)/Chapter 6",
            }
        ],
        13,
    ),
]
