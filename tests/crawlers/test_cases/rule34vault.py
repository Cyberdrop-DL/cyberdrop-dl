DOMAIN = "rule34vault"
TEST_CASES = [
    {
        "url": "https://rule34vault.com/post/1233301",
        "results": [
            {
                "url": "https://r34xyz.b-cdn.net/posts/1233/1233301/1233301.mp4",
                "filename": "1233301.mp4",
                "debrid_url": None,
                "original_filename": "1233301.mp4",
                "referer": "https://rule34vault.com/post/1233301",
                "album_id": None,
                "uploaded_at": 1779590974,
                "download_folder": "re:Loose Files (Rule34Vault)",
            }
        ],
        "count": 1,
    },
    {
        "url": "https://rule34vault.com/playlists/view/283077",
        "results": [
            {
                "url": "ANY",
                "album_id": "283077",
                "download_folder": "re:하츠네 미쿠 [playlist] (Rule34Vault)",
            },
        ],
        "count": 33,
    },
    {
        "url": "https://rule34vault.com/sarahvividart%7Calien",
        "results": [
            {
                "url": "ANY",
                "download_folder": "re:sarahvividart,alien [tags] (Rule34Vault)",
            },
        ],
        "count": range(50, 60),
    },
]
