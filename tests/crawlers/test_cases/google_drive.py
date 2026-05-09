DOMAIN = "drive.google"
TEST_CASES = [
    {
        "url": "https://drive.google.com/file/d/1F0YBsnQRvrMbK0p9UlnyLu88kqQ0j_F6/edit",
        "description": "small file with no warning",
        "results": [
            {
                "url": "ANY",
                "filename": "file-50MB.dat",
                "referer": "https://drive.google.com/file/d/1F0YBsnQRvrMbK0p9UlnyLu88kqQ0j_F6",
                "album_id": None,
                "uploaded_at": None,
            }
        ],
    },
    {
        "url": "https://drive.google.com/file/d/15WghIO0iwekXStmVWeK5HxC566iN41l6/view",
        "description": "small file with no warning",
        "results": [
            {
                "url": "ANY",
                "filename": "file-100MB.dat",
                "referer": "https://drive.google.com/file/d/15WghIO0iwekXStmVWeK5HxC566iN41l6",
                "album_id": None,
                "uploaded_at": None,
            }
        ],
    },
    {
        "url": "https://drive.usercontent.google.com/download?id=1fXgBupLzThTGLLsiYCHRQJixuDsR1bSI&export=download",
        "description": "file with warning doe to large size (529M)",
        "results": [
            {
                "url": "ANY",
                "filename": "cifar10_stats.npz",
                "referer": "https://drive.google.com/file/d/1fXgBupLzThTGLLsiYCHRQJixuDsR1bSI",
                "album_id": None,
                "uploaded_at": None,
            }
        ],
    },
    {
        "url": "https://drive.google.com/file/d/1WHv5Dm1GtrDZj-AxJZd3T-NMIBXty3eV/view",
        "description": """
        Huge file with warning do to large size (9.8G), this test may fail.
        Public download without an account are limited to about 5G per day and they return 429 with that happens""",
        "results": [
            {
                "url": "ANY",
                "filename": "bundle_cutouts_africa.zip",
                "referer": "https://drive.google.com/file/d/1WHv5Dm1GtrDZj-AxJZd3T-NMIBXty3eV",
                "album_id": None,
                "uploaded_at": None,
            }
        ],
    },
    {
        "url": "https://docs.google.com/document/d/1ZzEzJbemBMPm46O2q5VcGNoPbqDu9AhhUc2djQbvbTY/edit",
        "results": [
            {
                "url": "ANY",
                "filename": "test.docx",
                "referer": "https://docs.google.com/document/d/1ZzEzJbemBMPm46O2q5VcGNoPbqDu9AhhUc2djQbvbTY?format=docx",
                "album_id": None,
                "uploaded_at": None,
            }
        ],
    },
    {
        "url": "https://docs.google.com/document/d/1ZzEzJbemBMPm46O2q5VcGNoPbqDu9AhhUc2djQbvbTY?format=txt",
        "results": [
            {
                "url": "ANY",
                "filename": "test.txt",
                "referer": "https://docs.google.com/document/d/1ZzEzJbemBMPm46O2q5VcGNoPbqDu9AhhUc2djQbvbTY?format=txt",
                "album_id": None,
                "uploaded_at": None,
            }
        ],
    },
    {
        "url": "https://docs.google.com/document/d/1ZzEzJbemBMPm46O2q5VcGNoPbqDu9AhhUc2djQbvbTY?format=xlsx",
        "results": [
            {
                "url": "ANY",
                "filename": "test.docx",
                "referer": "https://docs.google.com/document/d/1ZzEzJbemBMPm46O2q5VcGNoPbqDu9AhhUc2djQbvbTY?format=docx",
                "album_id": None,
                "uploaded_at": None,
            }
        ],
    },
    {
        "url": "https://docs.google.com/spreadsheets/d/1E3LpudUdUZycJpxSKK-c9-oIDuJoo5_7/edit?format=ods",
        "description": "This is a spreeadsheet but the id is a normal file id. We won't be able to download it with a custom format",
        "results": [
            {
                "url": "ANY",
                "filename": "TK Online 1.5.xlsx",
                "referer": "https://drive.google.com/file/d/1E3LpudUdUZycJpxSKK-c9-oIDuJoo5_7",
                "album_id": None,
                "uploaded_at": None,
            }
        ],
    },
    {
        "url": "https://drive.google.com/file/d/0ByeS4oOUV-49Zzh4R1J6R09zazQ/edit",
        "description": "v0 file id (28 chars)",
        "results": [
            {
                "url": "ANY",
                "filename": "Big Buck Bunny.mp4",
                "referer": "https://drive.google.com/file/d/0ByeS4oOUV-49Zzh4R1J6R09zazQ",
                "album_id": None,
                "uploaded_at": None,
            }
        ],
    },
    {
        "url": "https://drive.google.com/uc?id=1IP0o8dHcQrIHGgVyp0Ofvx2cGfLzyO1x",
        "results": [
            {
                "url": "ANY",
                "filename": "My Buddy - Henry Burr - Gus Kahn - Walter Donaldson.mp3",
                "referer": "https://drive.google.com/file/d/1IP0o8dHcQrIHGgVyp0Ofvx2cGfLzyO1x",
                "album_id": None,
                "uploaded_at": None,
            }
        ],
    },
    {
        "url": "https://drive.google.com/drive/folders/1k8pgIaGw6PribxVqMgmDtlpzbUPJuzrX",
        "description": "Folder with +50 files",
        "results": [],
        "count": 135,
    },
]
