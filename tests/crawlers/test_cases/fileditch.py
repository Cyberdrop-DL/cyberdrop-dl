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
]
