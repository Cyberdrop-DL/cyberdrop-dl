DOMAIN = "imgbb"
TEST_CASES = [
    (
        "https://ibb.co/FbtMCg43",
        [
            {
                "url": "https://i.ibb.co/DDnyT5fW/Long-toes-are-the-best.jpg",
                "filename": "Long-toes-are-the-best.jpg",
                "referer": "https://ibb.co/FbtMCg43",
                "album_id": None,
                "datetime": 1740984052,
            }
        ],
    ),
    (
        "https://i.ibb.co/DDnyT5fW/Long-toes-are-the-best.jpg",
        [
            {
                "url": "https://i.ibb.co/DDnyT5fW/Long-toes-are-the-best.jpg",
                "filename": "Long-toes-are-the-best.jpg",
                "referer": "https://i.ibb.co/DDnyT5fW/Long-toes-are-the-best.jpg",
                "album_id": None,
                "datetime": None,
            }
        ],
    ),
    (
        "https://ibb.co/album/yhdTNv",
        [
            {
                "url": "re:.jpg",
                "album_id": "yhdTNv",
                "download_filename": r"re:ALEXA_2024/25 \(ImgBB\)",
                "datetime": None,
            }
        ],
        1537,
    ),
    (
        "https://ibb.co/album/DDcTkZ",
        [
            {
                "url": "https://i.ibb.co/xSSVZ3TF/FOISTUDIOS-arna-SET2-16.jpg",
                "filename": "FOISTUDIOS-arna-SET2-16.jpg",
                "referrer": "https://ibb.co/WWWSCsJV",
                "album_id": "DDcTkZ",
            },
            {
                "url": "https://i.ibb.co/3ytgckZy/FOISTUDIOS-arna-SET2-14.jpg",
                "filename": "FOISTUDIOS-arna-SET2-14.jpg",
                "referrer": "https://ibb.co/wND54YmN",
                "album_id": "DDcTkZ",
            },
            {
                "url": "https://i.ibb.co/gF3fc73F/FOISTUDIOS-arna-SET2-3.jpg",
                "filename": "FOISTUDIOS-arna-SET2-3.jpg",
                "referrer": "https://ibb.co/93N1dvN3",
                "album_id": "DDcTkZ",
            },
            {
                "url": "https://i.ibb.co/tPzBWLjm/FOISTUDIOS-arna-SET2-10.jpg",
                "filename": "FOISTUDIOS-arna-SET2-10.jpg",
                "referrer": "https://ibb.co/Z1Sdk24L",
                "album_id": "DDcTkZ",
            },
            {
                "url": "https://i.ibb.co/tTgcj5k9/FOISTUDIOS-arna-SET2-6.jpg",
                "filename": "FOISTUDIOS-arna-SET2-6.jpg",
                "referrer": "https://ibb.co/5gmvpVtP",
                "album_id": "DDcTkZ",
            },
            {
                "url": "https://i.ibb.co/sdMsb0YW/FOISTUDIOS-arna-SET2-7.jpg",
                "filename": "FOISTUDIOS-arna-SET2-7.jpg",
                "referrer": "https://ibb.co/Mx3PZY0B",
                "album_id": "DDcTkZ",
            },
            {
                "url": "https://i.ibb.co/sd5z3Mj5/FOISTUDIOS-arna-SET2-12.jpg",
                "filename": "FOISTUDIOS-arna-SET2-12.jpg",
                "referrer": "https://ibb.co/PvT0CfxT",
                "album_id": "DDcTkZ",
            },
            {
                "url": "https://i.ibb.co/nqMZF2ts/FOISTUDIOS-arna-SET2-17.jpg",
                "filename": "FOISTUDIOS-arna-SET2-17.jpg",
                "referrer": "https://ibb.co/7xt8qcLJ",
                "album_id": "DDcTkZ",
            },
            {
                "url": "https://i.ibb.co/G428GCFC/FOISTUDIOS-arna-SET2-13.jpg",
                "filename": "FOISTUDIOS-arna-SET2-13.jpg",
                "referrer": "https://ibb.co/wFWP8pYp",
                "album_id": "DDcTkZ",
            },
            {
                "url": "https://i.ibb.co/JF0FWGXz/FOISTUDIOS-arna-SET2-9.jpg",
                "filename": "FOISTUDIOS-arna-SET2-9.jpg",
                "referrer": "https://ibb.co/zHjHWBKS",
                "album_id": "DDcTkZ",
            },
        ],
        10,
    ),
]
