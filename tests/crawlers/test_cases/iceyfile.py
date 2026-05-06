DOMAIN = "iceyfile"
TEST_CASES = [
    {
        "url": "https://iceyfile.com/be60cca8a9dec177/fff.png",
        "description": "This will fail. iceyfile now always requires a 1 type access only captcha for individual files",
        "xfail": "This will fail. iceyfile now always requires a 1 type access only captcha for individual files",
        "results": [
            {
                "url": "re:https://srv1\\.iceyfile\\.net/be60cca8a9dec177/fff\\.png\\?download_token=",
                "filename": "fff",
                "referer": "https://iceyfile.com/be60cca8a9dec177/fff.png",
                "album_id": None,
                "uploaded_at": 1755488372,
            }
        ],
    },
    {
        "url": "https://iceyfile.com/folder/75061972f799eeacba32ac81f37493bc/CDL_test",
        "results": [
            {
                "url": "re:https://srv1\\.iceyfile\\.net/be60cca8a9dec177/fff\\.png\\?download_token=",
                "filename": "fff.png",
                "referer": "https://iceyfile.com/be60cca8a9dec177/fff.png",
                "download_folder": "re:CDL_test \\(Iceyfile\\)",
                "album_id": "75061972f799eeacba32ac81f37493bc",
                "uploaded_at": 1755491602,
            }
        ],
    },
]
