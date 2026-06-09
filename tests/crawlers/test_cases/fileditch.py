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
    {
        "url": "https://fileditchfiles.me/temp/d9dc8e3cc669f9d24b16/3840x2839_b545565c05a233584ef041f248a38426.jpg",
        "results": [
            {
                "url": "https://tempfileditchyall.me/temp/d9dc8e3cc669f9d24b16/3840x2839_b545565c05a233584ef041f248a38426.jpg?md5=JVoo-HxiBOROUtbiyfX4zg&expires=1781110320",
                "filename": "3840x2839_b545565c05a233584ef041f248a38426.jpg",
                "debrid_link": None,
                "original_filename": "3840x2839_b545565c05a233584ef041f248a38426.jpg",
                "referer": "https://fileditchfiles.me/temp/d9dc8e3cc669f9d24b16/3840x2839_b545565c05a233584ef041f248a38426.jpg",
                "album_id": None,
                "uploaded_at": None,
                "download_folder": "re:Loose Files (Fileditch)",
            }
        ],
        "count": 1,
    },
]
