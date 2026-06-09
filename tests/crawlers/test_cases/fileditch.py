DOMAIN = "fileditch"
TEST_CASES = [
    {
        "url": "https://fileditchfiles.me/file.php?f=/b71/FrmLzfLKUHBWDTQfqaTZ.mp4",
        "results": [
            {
                "url": "re:thegumonmyshoe.me/b71/FrmLzfLKUHBWDTQfqaTZ.mp4",
                "filename": "FrmLzfLKUHBWDTQfqaTZ.mp4",
                "referer": "https://fileditchfiles.me/file.php?f=/b71/FrmLzfLKUHBWDTQfqaTZ.mp4",
                "download_folder": "re:Loose Files (Fileditch)",
                "uploaded_at": None,
            }
        ],
    },
    {
        "url": "https://fileditchfiles.me//file.php?f=/b70/jRuBeGZlRoBWPurUARg.mp4",
        "description": "multiple slashes on URL",
        "results": [
            {
                "url": "re:thegumonmyshoe.me/b70/jRuBeGZlRoBWPurUARg.mp4",
                "referer": "https://fileditchfiles.me/file.php?f=/b70/jRuBeGZlRoBWPurUARg.mp4",
                "download_folder": "re:Loose Files (Fileditch)",
                "uploaded_at": None,
            }
        ],
    },
    {
        "url": "https://fileditchfiles.me/beta5/a292619a708980582542/%5B8.11%5D_valk1.mp4",
        "results": [
            {
                "url": "https://donotsharethesetemplinksyouidiot.st/beta5/a292619a708980582542/%5B8.11%5D_valk1.mp4?md5=WBrfgN6YCxEBPQGXaJqaeA&expires=1781110076",
                "filename": "[8.11]_valk1.mp4",
                "debrid_link": None,
                "original_filename": "[8.11]_valk1.mp4",
                "referer": "https://fileditchfiles.me/beta5/a292619a708980582542/%5B8.11%5D_valk1.mp4",
                "album_id": None,
                "uploaded_at": None,
                "download_folder": "re:Loose Files (Fileditch)",
            }
        ],
        "count": 1,
    },
]
