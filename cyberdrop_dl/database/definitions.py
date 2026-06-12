CREATE_HISTORY = """CREATE TABLE IF NOT EXISTS media (
  domain TEXT,
  url_path TEXT,
  referer TEXT,
  download_path TEXT,
  download_filename TEXT,
  original_filename TEXT,
  file_size INT,
  duration FLOAT,
  album_id TEXT,
  completed INTEGER NOT NULL,
  created_at TIMESTAMP,
  completed_at TIMESTAMP,
  PRIMARY KEY (domain, url_path, original_filename)
);"""

CREATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version VARCHAR(50) NOT NULL PRIMARY KEY,
    applied_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_FILES = """
CREATE TABLE IF NOT EXISTS files (
  folder TEXT,
  download_filename TEXT,
  original_filename TEXT,
  file_size INT,
  referer TEXT,
  date INT,
  PRIMARY KEY (folder, download_filename)
);

"""

CREATE_HASH = """
CREATE TABLE IF NOT EXISTS hash (
  folder TEXT,
  download_filename TEXT,
  hash_type TEXT,
  hash TEXT,
  PRIMARY KEY (folder, download_filename, hash_type),
  FOREIGN KEY (folder, download_filename) REFERENCES files(folder, download_filename)
);
"""


CREATE_HASH_INDEX = """
CREATE INDEX IF NOT EXISTS idx_hash_type_hash ON hash (hash_type, hash);
"""

CREATE_MEDIA_INDEX = """
CREATE INDEX IF NOT EXISTS idx_media_referer_completed
    ON media (referer, completed);

CREATE INDEX IF NOT EXISTS idx_media_domain_album
    ON media (domain, album_id);

CREATE INDEX IF NOT EXISTS idx_media_domain_url_path_referer
    ON media (domain, url_path, referer);

CREATE INDEX IF NOT EXISTS idx_media_domain_referer_completed
    ON media (domain, referer, completed);

"""
