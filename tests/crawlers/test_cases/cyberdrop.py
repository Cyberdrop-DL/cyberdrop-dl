DOMAIN = "cyberdrop"
TEST_CASES = [
    (
        "https://cyberdrop.cr/f/de155Wa0Z7OV59",
        [
            {
                "url": r"re:token",
                "filename": "0h07ynuksluicazppofcw_source-ClHET0f7.mp4",
                "original_filename": "0h07ynuksluicazppofcw_source-ClHET0f7.mp4",
                "referer": "https://cyberdrop.cr/f/de155Wa0Z7OV59",
                "album_id": None,
                "datetime": None,
            }
        ],
    ),
    (
        "https://k1-cd.cdn.gigachad-cdn.ru/api/file/d/de155Wa0Z7OV59?token=12345",
        [
            {
                "url": r"re:token",
                "filename": "0h07ynuksluicazppofcw_source-ClHET0f7.mp4",
                "original_filename": "0h07ynuksluicazppofcw_source-ClHET0f7.mp4",
                "referer": "https://cyberdrop.cr/f/de155Wa0Z7OV59",
                "album_id": None,
                "datetime": None,
            }
        ],
    ),
    (
        "https://cyberdrop.cr/0h07ynuksluicazppofcw_source-ClHET0f7.mp4",
        [
            {
                "url": r"re:token",
                "filename": "0h07ynuksluicazppofcw_source-ClHET0f7.mp4",
                "original_filename": "0h07ynuksluicazppofcw_source-ClHET0f7.mp4",
                "referer": "https://cyberdrop.cr/f/de155Wa0Z7OV59",
                "album_id": None,
                "datetime": None,
            }
        ],
    ),
    (
        "https://cyberdrop.cr/a/eEwua7SZ",
        [
            {
                "url": r"re:/api/file/d/",
                "referer": "re:https://cyberdrop.cr/f/",
                "download_folder": r"re:me1adinha \(Cyberdrop\)",
                "album_id": "eEwua7SZ",
                "datetime": 1635742800,
            }
        ],
        13,
    ),
]
