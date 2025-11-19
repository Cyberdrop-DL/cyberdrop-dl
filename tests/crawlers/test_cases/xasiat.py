DOMAIN = "xasiat"
TEST_CASES = [
    (
        "https://www.xasiat.com/albums/30487/cosplay-jk-61p-797mb",
        [
            {
                "url": "https://www.xasiat.com/get_image/2/01a28782c7940969a3a3d55ab1842268/sources/30000/30487/2155729.jpg/",
                "filename": "2155729.jpg",
                "referer": "https://www.xasiat.com/get_image/2/01a28782c7940969a3a3d55ab1842268/sources/30000/30487/2155729.jpg/",
                "album_id": "30487",
                "datetime": None,
                "download_folder": r"re:\[Cosplay\] 屿鱼 蔚蓝档案 妃咲 JK \[61P-797MB\] \[album\] \(Xasiat\)",
            }
        ],
        61,
    ),
    (
        "https://www.xasiat.com/videos/104092/dvd-ai-shinozaki-special-bonus-dvd-weekly-playboy-2023-09-18-no-38/",
        [
            {
                "url": "ANY",
                "filename": "+付録DVD Ai Shinozaki 篠崎愛 – Special Bonus DVD Weekly Playboy 2023-09-18 No.38 [104092].mp4",  # noqa: RUF001
                "original_filename": "104092_source.mp4",
                "album_id": None,
            }
        ],
    ),
]
