DOMAIN = "pawchive"
TEST_CASES = [
    {
        "url": "https://pawchive.pw/patreon/user/36069133/post/162746868",
        "results": [
            {
                "url": "https://file.pawchive.pw/data/a7/70/a7709ff3f6b955fc8e6e0c3ffac60e66e2ade2f0b29e26209e927557ef8dfd18.png?f=691949550.png",
                "filename": "691949550.png",
                "debrid_url": None,
                "original_filename": "691949550.png",
                "referer": "https://pawchive.pw/patreon/user/36069133/post/162746868",
                "album_id": "36069133",
                "uploaded_at": 1783094455,
                "download_folder": "re:Natalie Gold (Pawchive)",
                "thumbnail": None,
            },
        ],
        "count": 1,
    },
    {
        "url": "https://pawchive.pw/patreon/user/36069133/post/162746868",
        "description": "same post as above but with expand_posts enabled",
        "results": [
            {
                "url": "https://file.pawchive.pw/data/a7/70/a7709ff3f6b955fc8e6e0c3ffac60e66e2ade2f0b29e26209e927557ef8dfd18.png?f=691949550.png",
                "filename": "691949550.png",
                "debrid_url": None,
                "original_filename": "691949550.png",
                "referer": "https://pawchive.pw/patreon/user/36069133/post/162746868",
                "album_id": "36069133",
                "uploaded_at": 1783094455,
                "download_folder": "re:Natalie Gold (Pawchive)",
                "thumbnail": None,
            },
            {
                "url": "re:https://t1.pawchive.pw/v/2c09b3df25b88477/master.m3u8",
                "filename": "691871229 [avc1][mp4a][1080p].mp4",
                "debrid_url": None,
                "original_filename": "691871229.mp4",
                "referer": "https://pawchive.pw/patreon/user/36069133/post/162746868",
                "album_id": "36069133",
                "uploaded_at": 1783094455,
                "download_folder": "re:Natalie Gold (Pawchive)",
                "thumbnail": None,
            },
        ],
        "count": 2,
    },
    {
        "url": "https://pawchive.pw/patreon/user/48610247/post/144898011",
        "description": "malformed file.path with query params",
        "results": [
            {
                "url": "https://file.pawchive.pw/data/d5/ef/d5efd1b3d8c8f993203a14d018972c058bad47177d91a4fbe8777eb322a572ff.png?f=adverse-conditions-mockup-front.png?v%3D1749219392",
                "filename": "d5efd1b3d8c8f993203a14d018972c058bad47177d91a4fbe8777eb322a572ff.png",
                "debrid_url": None,
                "original_filename": "adverse-conditions-mockup-front.png?v=1749219392",
                "referer": "https://pawchive.pw/patreon/user/48610247/post/144898011",
                "album_id": "48610247",
                "uploaded_at": 1764686622,
                "download_folder": "re:Kill James Bond! (Pawchive)",
            },
        ],
        "count": 1,
    },
    {
        "url": "https://pawchive.pw/patreon/user/177727722",
        "results": [
            {
                "url": "re:https://file.pawchive.pw/data/",
                "debrid_url": None,
                "referer": "re:https://pawchive.pw/patreon/user/177727722/post/",
                "album_id": "177727722",
                "uploaded_at": int,
                "download_folder": "re:KRAPAO (Pawchive)",
            },
        ],
        "count": range(22, 30),
    },
]
