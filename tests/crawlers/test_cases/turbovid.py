DOMAIN = "turbovid"
TEST_CASES = [
    (
        "https://turbovid.cr/embed/E-26dWKftfB",
        [
            {
                "url": "re:/data/E-26dWKftfB.mp4",
                "filename": "E-26dWKftfB.mp4",
                "referer": "https://turbovid.cr/d/E-26dWKftfB",
                "album_id": None,
                "uploaded_at": 1749272400,
            }
        ],
    ),
    (
        "https://turbo.cr/embed/E-26dWKftfB",
        [
            {
                "url": "re:/data/E-26dWKftfB.mp4",
                "filename": "E-26dWKftfB.mp4",
                "referer": "https://turbovid.cr/d/E-26dWKftfB",
                "album_id": None,
                "uploaded_at": 1749272400,
            }
        ],
    ),
    (
        "https://turbovid.cr/a/Bls2Yfbxco0",
        [
            {
                "url": "re:/data/LM54NzGj8PO.mp4",
                "filename": "LM54NzGj8PO.mp4",
                "referer": "https://turbovid.cr/d/LM54NzGj8PO",
                "download_folder": "re:Qoqsik (TurboVid)",
                "album_id": "Bls2Yfbxco0",
                "uploaded_at": 1763269200,
            }
        ],
    ),
    (
        "https://cdn4.turbovid.cr/data/E-26dWKftfB.mp4",
        [
            {
                "url": "re:/data/E-26dWKftfB.mp4",
                "filename": "E-26dWKftfB.mp4",
                "referer": "https://cdn4.turbovid.cr/data/E-26dWKftfB.mp4",
                "album_id": None,
                "uploaded_at": None,
            }
        ],
    ),
    (
        "https://turbo.cr/d/G4BfcI6TOKsLY",
        [
            {
                "url": "re:/data/G4BfcI6TOKsLY.mp4",
                "filename": "Grumpy Cat.mp4",
                "original_filename": "Grumpy Cat.mp4",
                "album_id": None,
                "uploaded_at": 1770872400,
            }
        ],
    ),
    ("https://turbovid.cr/library?q=mirror", [], range(60, 80)),
]
