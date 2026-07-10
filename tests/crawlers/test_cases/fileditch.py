DOMAIN = "fileditch"
TEST_CASES = [
    {
        "url": "https://fileditchfiles.me/file.php?f=/b71/FrmLzfLKUHBWDTQfqaTZ.mp4",
        "results": [
            {
                "url": "re:/b71/FrmLzfLKUHBWDTQfqaTZ.mp4?md5=",
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
                "url": "re:/b70/jRuBeGZlRoBWPurUARg.mp4?md5=",
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
                "url": "re:/beta5/a292619a708980582542/%5B8.11%5D_valk1.mp4?md5=",
                "filename": "[8.11]_valk1.mp4",
                "original_filename": "[8.11]_valk1.mp4",
                "referer": "https://fileditchfiles.me/beta5/a292619a708980582542/%5B8.11%5D_valk1.mp4",
                "album_id": None,
                "uploaded_at": None,
                "download_folder": "re:Loose Files (Fileditch)",
            }
        ],
        "count": 1,
    },
    {
        "url": "https://fileditchfiles.me/alpha7/adf9b7514d0d86d1cadd/Anai_Loves_-_Cheating_At_The_World_Cup_Match_1080p.mp4",
        "results": [
            {
                "url": "re:/alpha7/adf9b7514d0d86d1cadd/Anai_Loves_-_Cheating_At_The_World_Cup_Match_1080p.mp4?md5=",
                "filename": "Anai_Loves_-_Cheating_At_The_World_Cup_Match_1080p.mp4",
                "original_filename": "Anai_Loves_-_Cheating_At_The_World_Cup_Match_1080p.mp4",
                "referer": "https://fileditchfiles.me/alpha7/adf9b7514d0d86d1cadd/Anai_Loves_-_Cheating_At_The_World_Cup_Match_1080p.mp4",
                "album_id": None,
                "uploaded_at": None,
                "download_folder": "re:Loose Files (Fileditch)",
            }
        ],
        "count": 1,
    },
]
