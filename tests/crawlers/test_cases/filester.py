DOMAIN = "filester"
TEST_CASES = [
    (
        "https://filester.me/d/Y9Vkbpq",
        [
            {
                "url": "re:.filester.me/d/",
                "filename": "lilcanadiangirl_Stranger-in-the-Theatre.mp4",
                "referer": "https://filester.me/d/Y9Vkbpq",
                "album_id": None,
                "uploaded_at": 1771027200,
            }
        ],
    ),
    (
        "https://filester.me/d/4h9lQtR",
        [
            {
                "url": "re:.filester.me/d/",
                "filename": "Linda Lan - Meanbitches slave orders.mp4",
                "album_id": None,
            }
        ],
    ),
    (
        "https://filester.me/f/c3bf3e1da9982845",
        [
            {
                "url": "re:.filester.me/d/",
                "download_folder": "re:mirror_post-410_1771095844 (Filester)",
                "album_id": "c3bf3e1da9982845",
            }
        ],
        53,
    ),
    (
        "https://filester.me/f/c1a31c9ca510870b",
        [
            {
                "url": "re:.filester.me/d/",
                "download_folder": "re:Natalie (Filester)/Pics",
            }
        ],
        range(150, 160),
    ),
]
