DOMAIN = "porntrex"
TEST_CASES = [
    (
        "https://www.porntrex.com/video/3001819/a-pandemic-will-not-stop-the-two-lovers",
        [
            {
                "url": "https://www.porntrex.com/video/3001819",
                "debrid_url": "re:/get_file/",
                "filename": "A pandemic will not stop the two lovers [3001819][1080p].mp4",
                "original_filename": "3001819_1080p.mp4",
                "download_folder": "re:Loose Files (Porntrex)",
                "referer": "https://www.porntrex.com/video/3001819",
                "datetime": None,
            }
        ],
    ),
    (
        "https://www.porntrex.com/search/song/",
        [
            {
                "url": "ANY",
                "download_folder": "re:song [search] (Porntrex)",
                "album_id": None,
            },
        ],
        range(255, 300),
    ),
    (
        "https://www.porntrex.com/albums/57737/brandi-love-set-35/",
        [
            {
                "url": "re:/get_image/",
                "referer": "https://www.porntrex.com/albums/57737/brandi-love-set-35/",
                "download_folder": "re:Brandi Love SET 35 (Porntrex)",
                "datetime": None,
                "album_id": "57737",
            },
        ],
        376,
    ),
]
