DOMAIN = "saint"
TEST_CASES = [
    (
        "https://saint2.su/embed/E-26dWKftfB",
        [
            {
                "url": "https://data.saint2.cr/data/E-26dWKftfB.mp4",
                "filename": "E-26dWKftfB.mp4",
                "referer": "https://saint2.su/embed/E-26dWKftfB",
                "album_id": None,
                "datetime": None,
            }
        ],
    ),
    (
        "https://saint2.cr/a/Bls2Yfbxco0",
        [
            {
                "url": "https://data.saint2.cr/data/LM54NzGj8PO.mp4",
                "filename": "LM54NzGj8PO.mp4",
                "referer": "https://saint2.su/d/TE01NE56R2o4UE8ubXA0",
                "album_id": "Bls2Yfbxco0",
                "datetime": None,
            }
        ],
    ),
    (
        "https://saint2.su/d/TE01NE56R2o4UE8ubXA0",
        [
            {
                "url": "https://data.saint2.cr/data/LM54NzGj8PO.mp4",
                "filename": "LM54NzGj8PO.mp4",
                "referer": "https://saint2.su/d/TE01NE56R2o4UE8ubXA0",
                "album_id": None,
                "datetime": None,
            }
        ],
    ),
    (
        "https://data.saint2.cr/data/LM54NzGj8PO.mp4",
        [
            {
                "url": "https://data.saint2.cr/data/LM54NzGj8PO.mp4",
                "filename": "LM54NzGj8PO.mp4",
                "referer": "https://data.saint2.cr/data/LM54NzGj8PO.mp4",
                "album_id": None,
                "datetime": None,
            }
        ],
    ),
    ("https://saint2.su/library/search/mirror", [], 45),
]
