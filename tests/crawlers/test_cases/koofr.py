DOMAIN = "koofr"
TEST_CASES = [
    (
        "https://k00.fr/sngg51ex?password=756626",
        [
            {
                "url": "https://app.koofr.net/content/links/b0299c24-366a-4a61-b395-dc4fa3d7781e/files/get/Cyberdrop-DL.v8.4.0.zip?password=756626&path=/",
                "filename": "Cyberdrop-DL.v8.4.0.zip",
                "referer": "https://app.koofr.net/links/b0299c24-366a-4a61-b395-dc4fa3d7781e?password=756626",
                "album_id": None,
                "datetime": 1761254288,
            }
        ],
    ),
    (
        "https://k00.fr/b372of1c",
        [
            {
                "url": "https://app.koofr.net/content/links/0a00467b-2901-4213-8d71-44fad80de82d/files/get/Cyberdrop-DL.v8.4.0.zip?path=/Cyberdrop-DL.v8.4.0.zip",
                "filename": "Cyberdrop-DL.v8.4.0.zip",
                "referer": "https://app.koofr.net/links/0a00467b-2901-4213-8d71-44fad80de82d",
                "album_id": "0a00467b-2901-4213-8d71-44fad80de82d",
                "download_folder": r"re:CDL test \(Koofr\)",
            },
            {
                "url": "https://app.koofr.net/content/links/0a00467b-2901-4213-8d71-44fad80de82d/files/get/start_linux.sh?path=/subfolder/start_linux.sh",
                "filename": "start_linux.sh",
                "referer": "https://app.koofr.net/links/0a00467b-2901-4213-8d71-44fad80de82d?path=/subfolder",
                "album_id": "0a00467b-2901-4213-8d71-44fad80de82d",
                "download_folder": r"re:CDL test \(Koofr\)/subfolder",
            },
            {
                "url": "https://app.koofr.net/content/links/0a00467b-2901-4213-8d71-44fad80de82d/files/get/start_windows.bat?path=/subfolder/start_windows.bat",
                "filename": "start_windows.bat",
                "referer": "https://app.koofr.net/links/0a00467b-2901-4213-8d71-44fad80de82d?path=/subfolder",
                "album_id": "0a00467b-2901-4213-8d71-44fad80de82d",
                "download_folder": r"re:CDL test \(Koofr\)/subfolder",
            },
        ],
    ),
]
