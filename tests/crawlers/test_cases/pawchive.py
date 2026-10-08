DOMAIN = "pawchive"
TEST_CASES = [
    {
        "url": "https://pawchive.pw/patreon/user/36069133/post/162746868",
        "description": "temp deferred file",
        "results": [
            {
                "url": "https://file.pawchive.pw/data/1c/b2/1cb2f6f255bedc49f08fc42af294017ef24d6b62001da3c137d04e3619f8259b.jpg?f=thumbnail.jpg",
                "filename": "thumbnail.jpg",
                "debrid_url": None,
                "original_filename": "thumbnail.jpg",
                "referer": "https://pawchive.pw/patreon/user/36069133/post/162746868",
                "album_id": "36069133",
                "uploaded_at": 1783094455,
                "download_folder": "re:Natalie Gold (Pawchive)",
                "thumbnail": None,
            },
            {
                "url": "re:https://t1.pawchive.pw/d",
                "filename": "691871229.mp4",
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
        "url": "https://t1.pawchive.pw/d/2c09b3df25b88477/691871229.mp4?e=1791096166&s=16401b90519cd247cb387e9e5f19efd0",
        "description": "temp deferred file",
        "results": [
            {
                "url": "https://t1.pawchive.pw/d/2c09b3df25b88477/691871229.mp4?e=1791096166&s=16401b90519cd247cb387e9e5f19efd0",
                "filename": "691871229.mp4",
                "debrid_url": None,
                "original_filename": "691871229.mp4",
                "referer": "https://t1.pawchive.pw/d/2c09b3df25b88477/691871229.mp4?e=1791096166&s=16401b90519cd247cb387e9e5f19efd0",
                "album_id": None,
                "uploaded_at": None,
                "download_folder": "re:Loose Files (Pawchive)",
                "thumbnail": None,
            }
        ],
        "count": 1,
    },
    {
        "url": "https://pawchive.pw/patreon/user/48610247/post/144898011",
        "description": "malformed file.path with query params",
        "results": [
            {
                "url": "https://file.pawchive.pw/data/d5/ef/d5efd1b3d8c8f993203a14d018972c058bad47177d91a4fbe8777eb322a572ff.png?f=adverse-conditions-mockup-front.png",
                "filename": "adverse-conditions-mockup-front.png",
                "debrid_url": None,
                "original_filename": "adverse-conditions-mockup-front.png",
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
        "count": range(32, 40),
    },
]
