DOMAIN = "girlsreleased"
TEST_CASES = [
    (
        "https://girlsreleased.com/set/152521",
        [
            {
                "url": "re:imx.to",
                "filename": "re:DSC_",
                "download_folder": r"re:2025-11-19 - 152521 - Nike (GirlsReleased)",
                "referer": "ANY",
                "album_id": "152521",
                "datetime": 1763542843,
            }
        ],
        10,
    ),
    (
        "https://girlsreleased.com/model/11975/Poppy",
        [
            {
                "url": "re:imx.to",
                "download_folder": "re:Poppy [model] (GirlsReleased)/",
            }
        ],
        10,
    ),
    (
        "https://girlsreleased.com/site/modelsofboston.club/model/12022/Ashley",
        [
            {
                "url": "re:imx.to",
                "download_folder": "re:modelsofboston.club [site] (GirlsReleased)/Ashley [model]/",
            }
        ],
        10,
    ),
]
