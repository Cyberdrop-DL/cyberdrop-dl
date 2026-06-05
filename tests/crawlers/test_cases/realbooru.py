DOMAIN = "realbooru"
TEST_CASES = [
    {
        "url": "https://realbooru.com/index.php?page=post&s=view&id=917661",
        "results": [
            {
                "url": "https://realbooru.com//images/66/6e/666e45c4736b1a0618511086c71f711f.gif",
                "filename": "666e45c4736b1a0618511086c71f711f.gif",
                "debrid_link": None,
                "original_filename": "666e45c4736b1a0618511086c71f711f.gif",
                "referer": "https://realbooru.com/index.php?page=post&s=view&id=917661",
                "album_id": None,
                "uploaded_at": None,
                "download_folder": "re:Loose Files (RealBooru)",
            }
        ],
        "count": 1,
    },
    {
        "url": "https://realbooru.com/index.php?page=post&s=view&id=728477",
        "results": [
            {
                "url": "https://realbooru.com//images/2f/4b/2f4b948ff8de931e75173114969a8c25.mp4",
                "filename": "2f4b948ff8de931e75173114969a8c25.mp4",
                "debrid_link": None,
                "original_filename": "2f4b948ff8de931e75173114969a8c25.mp4",
                "referer": "https://realbooru.com/index.php?page=post&s=view&id=728477",
                "album_id": None,
                "uploaded_at": None,
                "download_folder": "re:Loose Files (RealBooru)",
            }
        ],
        "count": 1,
    },
    {
        "url": "https://realbooru.com/index.php?page=post&s=list&tags=dance",
        "results": [
            {
                "url": "ANY",
                "album_id": None,
                "uploaded_at": None,
                "download_folder": "re:dance (RealBooru)",
            },
        ],
        "count": range(52, 80),
    },
]
