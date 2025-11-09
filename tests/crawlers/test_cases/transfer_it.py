import re

DOMAIN = "transfer.it"
TEST_CASES = [
    (
        "https://transfer.it/t/yhWbjogXxRLL",
        [
            {
                "url": "https://bt7.api.mega.co.nz/cs/g?x=yhWbjogXxRLL&n=qgxVBD5D&fn=start_linux.sh",
                "filename": "start_linux.sh",
                "referer": "https://transfer.it/t/yhWbjogXxRLL#qgxVBD5D",
                "download_folder": "re:" + re.escape("CDL test transfer (Transfer.it)/test/Cyberdrop-DL.v8.4.0"),
                "datetime": 1762696355,
                "album_id": "yhWbjogXxRLL",
            },
            {
                "url": "https://bt7.api.mega.co.nz/cs/g?x=yhWbjogXxRLL&n=7lhHmJga&fn=start_windows.bat",
                "filename": "start_windows.bat",
                "referer": "https://transfer.it/t/yhWbjogXxRLL#7lhHmJga",
                "download_folder": "re:" + re.escape("CDL test transfer (Transfer.it)/test/Cyberdrop-DL.v8.4.0"),
                "datetime": 1762696355,
                "album_id": "yhWbjogXxRLL",
            },
            {
                "url": "https://bt7.api.mega.co.nz/cs/g?x=yhWbjogXxRLL&n=OxwHBbaa&fn=Cyberdrop-DL.v8.4.0.zip",
                "filename": "Cyberdrop-DL.v8.4.0.zip",
                "referer": "https://transfer.it/t/yhWbjogXxRLL#OxwHBbaa",
                "download_folder": "re:" + re.escape("CDL test transfer (Transfer.it)/test"),
                "datetime": 1762696355,
                "album_id": "yhWbjogXxRLL",
            },
        ],
    ),
]
