DOMAIN = "turbovid.cr"
TEST_CASES = [
    (
        "https://turbovid.cr/embed/E-26dWKftfB",
        [
            {
                "url": "re:turbovid.cr/data/E-26dWKftfB.mp4",
                "filename": "E-26dWKftfB.mp4",
                "referer": "https://turbovid.cr/d/E-26dWKftfB",
                "album_id": None,
                "datetime": 1749272400,
            }
        ],
    ),
    (
        "https://turbo.cr/embed/E-26dWKftfB",
        [
            {
                "url": "re:turbovid.cr/data/E-26dWKftfB.mp4",
                "filename": "E-26dWKftfB.mp4",
                "referer": "https://turbovid.cr/d/E-26dWKftfB",
                "album_id": None,
                "datetime": 1749272400,
            }
        ],
    ),
    (
        "https://turbovid.cr/a/Bls2Yfbxco0",
        [
            {
                "url": "re:turbovid.cr/data/LM54NzGj8PO.mp4",
                "filename": "LM54NzGj8PO.mp4",
                "referer": "https://turbovid.cr/d/LM54NzGj8PO",
                "download_folder": "re:Qoqsik (TurboVid)",
                "album_id": "Bls2Yfbxco0",
                "datetime": 1763269200,
            }
        ],
    ),
    (
        "https://cdn4.turbovid.cr/data/E-26dWKftfB.mp4",
        [
            {
                "url": "re:turbovid.cr/data/E-26dWKftfB.mp4",
                "filename": "E-26dWKftfB.mp4",
                "referer": "https://cdn4.turbovid.cr/data/E-26dWKftfB.mp4",
                "album_id": None,
                "datetime": None,
            }
        ],
    ),
    ("https://turbovid.cr/library?q=mirror", [], range(50, 60)),
]
