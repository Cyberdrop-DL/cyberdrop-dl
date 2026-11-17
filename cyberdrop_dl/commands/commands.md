# cyberdrop-dl

```console
cyberdrop-dl COMMAND [OPTIONS]
```

Run 'cyberdrop-dl' without arguments to start the interactive TUI

## Table of Contents

- [`show`](#cyberdrop-dl-show)
- [`report`](#cyberdrop-dl-report)
- [`download`](#cyberdrop-dl-download)
- [`database`](#cyberdrop-dl-database)
    - [`prune`](#cyberdrop-dl-database-prune)
        - [`hashes`](#cyberdrop-dl-database-prune-hashes)
    - [`transfer`](#cyberdrop-dl-database-transfer)
    - [`file`](#cyberdrop-dl-database-file)
    - [`dir`](#cyberdrop-dl-database-dir)
- [`cleanup`](#cyberdrop-dl-cleanup)
    - [`files`](#cyberdrop-dl-cleanup-files)
- [`config`](#cyberdrop-dl-config)
    - [`file`](#cyberdrop-dl-config-file)
    - [`edit`](#cyberdrop-dl-config-edit)
    - [`fill`](#cyberdrop-dl-config-fill)
    - [`new`](#cyberdrop-dl-config-new)
    - [`dir`](#cyberdrop-dl-config-dir)
- [`cache`](#cyberdrop-dl-cache)
    - [`file`](#cyberdrop-dl-cache-file)
    - [`clear`](#cyberdrop-dl-cache-clear)
    - [`dir`](#cyberdrop-dl-cache-dir)
- [`retry`](#cyberdrop-dl-retry)
    - [`failed`](#cyberdrop-dl-retry-failed)
    - [`all`](#cyberdrop-dl-retry-all)
- [`hash`](#cyberdrop-dl-hash)
- [`docs`](#cyberdrop-dl-docs)

**Commands**:

* [`cache`](#cyberdrop-dl-cache): Cache operations
* [`cleanup`](#cyberdrop-dl-cleanup): Perform maintenance tasks
* [`config`](#cyberdrop-dl-config): Config file operations
* [`database`](#cyberdrop-dl-database): Commands for managing the database
* [`docs`](#cyberdrop-dl-docs): Show documentation for every command
* [`download`](#cyberdrop-dl-download): Download URLs
* [`hash`](#cyberdrop-dl-hash): Compute and save hashes of every file in a folder (recursively)
* [`report`](#cyberdrop-dl-report): Generate and display information about the system
* [`retry`](#cyberdrop-dl-retry): Retry downloads from the database
* [`show`](#cyberdrop-dl-show): Show a list of all supported sites

**Parameters**:

* `--input-file, --input, -i PATH`: Text/HTML file with URL(s) to download
* `--config-file, --config, -c PATH`: YAML file to use as config
* `--cache-file PATH`: JSON file to use as cache
* `--database-file, --db PATH`: SQLite file to use as database

## cyberdrop-dl show

```console
cyberdrop-dl show [OPTIONS]
```

Show a list of all supported sites

**Parameters**:

* `--json, --no-json`: Output full site information as a JSON array *[default: False]*

## cyberdrop-dl report

```console
cyberdrop-dl report
```

Generate and display information about the system

## cyberdrop-dl download

```console
cyberdrop-dl download [OPTIONS] [ARGS...]
```

Download URLs

**Arguments**:

* `URLS_OR_FILES`: File(s)/ URL(s) to download

**Parameters**:

* `--input-file PATH`: Text/HTML file with URL(s) to download
* `--input-folder PATH`: Read all '.txt' within this folder for URL(s) to download (non recursive).
                All URLs within the same file will be grouped in the own subfolder (the filename) within the downloads folder
* `--input, -i PATH`: File/folder with URL(s) to download (non recursive)
* `--config-file, --config, -c PATH`: YAML file to use as config
* `--cache-file PATH`: JSON file to use as cache
* `--database-file, --db PATH`: SQLite file to use as database
* `--cookies PATH`: File/folder to import cookies from (.txt Netscape files)
* `--deep-scrape, --no-deep-scrape`: Make additional requests while scraping (slower) *[default: False]*
* `--delete-empty-folders, --no-delete-empty-folders`: Delete empty files and folders after a run *[default: True]*
* `--delete-partial-files, --no-delete-partial-files`: Delete partial files after a run *[default: False]*
* `--download-folder, --output, -o, -d PATH`: Base output path for all downloads *[default: downloads/cyberdrop-dl]*
* `--dump-json, -j, --no-dump-json`: Save details about each file (both skipped and downloaded) to a .jsonl file *[default: False]*
* `--ignore-history, --no-ignore-history`: Download files even if the already are marked as downloaded on the database *[default: False]*
* `--ignore-hashes, --no-ignore-hashes`: Download files even if their hash matches a file downloaded on the database *[default: False]*
* `--max-file-name-length INT`: Max number of characters a filename should have. Filenames longer that this will be truncated *[default: 95]*
* `--max-folder-name-length INT`: Max number of characters a folder should have. Filenames longer that this will be truncated *[default: 60]*
* `--max-thread-depth INT`: Restricts how many levels of nested threads are scraped on a forum *[default: 0]*
* `--max-thread-folder-depth INT`: Max number of nested folders CDL will create when maximum_thread_depth is greater that 0
* `--min-free-space BYTESIZE`: Minimum free space require to start new downloads *[default: 5368709120]*
* `--mtime, --no-mtime`: Use original upload date as modification date for downloaded file *[default: True]*
* `--restrict-path, --restrict-filenames CHOICE...`: *[choices: unix, windows, no_emoji, ascii]* *[default: ()]*
* `--update-check, -U, --no-update-check`: Check for updates at the end of the session *[default: True]*

**Crawlers**:

* `--crawlers.disabled STR...`: Name of crawlers to disable for the current run *[default: {}]*
* `--crawlers.bandcamp.formats CHOICE...`: Format to choose for downloads (if available), ordered by preference *[choices: mp3-320, mp3, aac-hi, wav, flac, vorbis, aiff, alas]* *[default: ('mp3-320', 'mp3', 'aac-hi', 'wav', 'flac', 'vorbis', 'aiff', 'alas')]*
* `--crawlers.bluesky.external, --crawlers.bluesky.no-external`: Parse and download embeds from third-party sites *[default: True]*
* `--crawlers.bluesky.threads, --crawlers.bluesky.no-threads`: Downloads all posts in a thread (All direct replies from OP to their own post) *[default: True]*
* `--crawlers.bluesky.content-urls, --crawlers.bluesky.no-content-urls`: Parse and try to download any URL found inside the text of a post *[default: True]*
* `--crawlers.bluesky.reposts, --crawlers.bluesky.no-reposts`: Download media from reposts in the user's timeline *[default: False]*
* `--crawlers.clonr.use-source, --crawlers.clonr.no-use-source`: Ignore files in clone and process the original Mega.nz URL *[default: False]*
* `--crawlers.clonr.zip, --crawlers.clonr.no-zip`: Download entire clone as a single ZIP file *[default: False]*
* `--crawlers.clypit.prefer-mp3, --crawlers.clypit.no-prefer-mp3`: Download audios as .mp3 files even if WAV (high quality) versions are available *[default: False]*
* `--crawlers.generic.wordpress-media URL...`: *[default: ()]*
* `--crawlers.generic.wordpress-html URL...`: *[default: ()]*
* `--crawlers.generic.discourse URL...`: *[default: ()]*
* `--crawlers.generic.chevereto URL...`: *[default: ()]*
* `--crawlers.generic.kvs URL...`: *[default: ()]*
* `--crawlers.generic.video URL...`: *[default: ()]*
* `--crawlers.generic.peertube URL...`: *[default: ()]*
* `--crawlers.generic.patreon URL...`: *[default: ()]*
* `--crawlers.google-drive.default-formats.docs CHOICE`: Default format for documents (can be overridden per URL with the 'format' query param) *[choices: docx, odt, rtf, txt, epub, pdf, md, zip]* *[default: docx]*
* `--crawlers.google-drive.default-formats.sheets CHOICE`: Default format for spreedsheets (can be overridden per URL with the 'format' query param) *[choices: xlsx, ods, html, csv, tsv]* *[default: xlsx]*
* `--crawlers.google-drive.default-formats.slides CHOICE`: Default format for presentations (can be overridden per URL with the 'format' query param) *[choices: pptx, odp]* *[default: pptx]*
* `--crawlers.octave-music.quality CHOICE`: Quality of audio file to download (lossless are .flac files) *[choices: lossless, mp3-320]* *[default: mp3-320]*
* `--crawlers.octave-music.filename-format STR`: Format to generate audio file *[default: {artist} - {title}{ext}]*
* `--crawlers.one-pace.prefer-dub, --crawlers.one-pace.no-prefer-dub`: Download episodes with english audio tracks instead of japanese (if available) *[default: False]*
* `--crawlers.only-haven.file, --crawlers.only-haven.no-file`: Download the main file in a post (if any) *[default: True]*
* `--crawlers.only-haven.attachments, --crawlers.only-haven.no-attachments`: Download all attachments in a post (may or may not include `file`) *[default: True]*
* `--crawlers.only-haven.content-urls, --crawlers.only-haven.no-content-urls`: Download any URL found inside the description (text) of a post *[default: True]*
* `--crawlers.only-haven.expand-posts, --crawlers.only-haven.no-expand-posts`: Make an additional API request for each post to get original filenames and the content/text (slower) *[default: False]*
* `--crawlers.only-haven.embed, --crawlers.only-haven.no-embed`: Download the embedded file from third party sites (if any)(mega.nz, pcloud, dropbox, etc..) *[default: True]*
* `--crawlers.patreon.content-urls, --crawlers.patreon.no-content-urls`: Download any URL found inside the description (text) of a post *[default: True]*
* `--crawlers.pawchive.file, --crawlers.pawchive.no-file`: Download the main file in a post (if any) *[default: True]*
* `--crawlers.pawchive.attachments, --crawlers.pawchive.no-attachments`: Download all attachments in a post (may or may not include `file`) *[default: True]*
* `--crawlers.pawchive.content-urls, --crawlers.pawchive.no-content-urls`: Download any URL found inside the description (text) of a post *[default: True]*
* `--crawlers.pawchive.expand-posts, --crawlers.pawchive.no-expand-posts`: Make an additional API request for each post to get original filenames and the content/text (slower) *[default: False]*
* `--crawlers.pawchive.embed, --crawlers.pawchive.no-embed`: Download the embedded file from third party sites (if any)(mega.nz, pcloud, dropbox, etc..) *[default: True]*
* `--crawlers.pornhub.profile-paths STR...`: Subpaths to scrape when an input URL is a profile's homepage *[default: ('photos/public', 'gifs/public', 'videos', 'videos/upload')]*
* `--crawlers.reddit.api CHOICE`: *[choices: arctic_shift]* *[default: arctic_shift]*
* `--crawlers.reddit.content-urls, --crawlers.reddit.no-content-urls`: Download any URL found inside the description (text) of a post *[default: True]*
* `--crawlers.reddit.crossposts, --crawlers.reddit.no-crossposts`: Download media in crossposts from another subreddit *[default: True]*
* `--crawlers.reddit.video-previews, --crawlers.reddit.no-video-previews`: Download video previews generated by reddit for externally content hosted *[default: False]*
* `--crawlers.tiktok.original, --crawlers.tiktok.no-original`: Download videos in original quality (slower) *[default: False]*
* `--crawlers.twitter.cards, --crawlers.twitter.no-cards`: Parse and download cards in a post (embeds from third-party sites) *[default: True]*
* `--crawlers.twitter.threads, --crawlers.twitter.no-threads`: Downloads all posts in a thread (All direct replies from OP to their own tweet) *[default: True]*
* `--crawlers.twitter.content-urls, --crawlers.twitter.no-content-urls`: Parse and try to download any URL found inside the text of a tweet *[default: True]*
* `--crawlers.twitter.articles.cover, --crawlers.twitter.articles.no-cover`: Download the cover image of articles *[default: True]*
* `--crawlers.twitter.articles.media, --crawlers.twitter.articles.no-media`: Download media files in the body of articles *[default: True]*
* `--crawlers.twitter.retweets, --crawlers.twitter.no-retweets`: Download media from retweets in the user's timeline *[default: False]*
* `--crawlers.twitter.image-size CHOICE`: *[choices: orig, 4096x4096, large, medium, small, thumb]* *[default: orig]*
* `--crawlers.vk.wall-filter CHOICE`: Which posts to download while scraping an user's wall *[choices: all, others, owner]* *[default: all]*

**Downloads**:

* `--downloads INT`: Max number of files to download simultaneously *[default: 15]*
* `--downloads.per-domain INT`: Max number of files to download simultaneously per domain *[default: 5]*
* `--attempts INT`: *[default: 2]*
* `--delay FLOAT`: Number of seconds to wait before starting downloads *[default: 0.0]*
* `--slow-speed BYTESIZE`: Skip downloads if their speed is below this value for more than 10 seconds. Set to 0 to disable *[default: 0]*
* `--speed-limit BYTESIZE`: Max speed rate (in bytes per second) to limit downloads (combined) *[default: 0]*
* `--back-pressure, --no-back-pressure`: Throttle scrape requests if there are too many downloads queued for the same site *[default: True]*
* `--jitter FLOAT`: Wait a random additional number of seconds in between 0 and <jitter> before downloads *[default: 0]*
* `--skip-and-mark-completed, --no-skip-and-mark-completed`: Skip all downloads and mark them as downloaded on the database *[default: False]*
* `--concurrent-segments INT`: Allow up to `<N>` HLS segments to be downloaded concurrently *[default: 10]*

**Filters**:

* `--audio, --no-audio`: Download/skip audio files *[default: True]*
* `--images, --no-images`: Download/skip image files *[default: True]*
* `--videos, --no-videos`: Download/skip videos *[default: True]*
* `--non-media, --no-non-media`: Download/skip non media files (.txt, zip, .rar, etc...) *[default: True]*
* `--thumbnails, --no-thumbnails`: Download/skip thumbnails of media files (if available) *[default: False]*
* `--image.size.min BYTESIZE`:
* `--image.size.max BYTESIZE`:
* `--video.size.min BYTESIZE`:
* `--video.size.max BYTESIZE`:
* `--audio.size.min BYTESIZE`:
* `--audio.size.max BYTESIZE`:
* `--non_media.size.min BYTESIZE`:
* `--non_media.size.max BYTESIZE`:
* `--video.duration.min TIMEDELTA`:
* `--video.duration.max TIMEDELTA`:
* `--audio.duration.min TIMEDELTA`:
* `--audio.duration.max TIMEDELTA`:
* `--before DATE`: Only download files uploaded before this date
* `--after DATE`: Only download files uploaded after this date
* `--filename-regex PATTERN[STR]`: Only download files that match this regex
* `--filename-regex-exclude PATTERN[STR]`: Do NOT download files that match this regex
* `--only-hosts STR...`: Only scrape/download from these domains *[default: {}]*
* `--skip-hosts STR...`: Skip scrape/download from these domains *[default: {}]*
* `--allow-files-with-no-extension, --no-allow-files-with-no-extension`: Download potentially dangerous files that have no extension *[default: False]*

**Hashing**:

* `--hashing CHOICE`: *[choices: off, in-place, post-download]* *[default: in-place]*
* `--hashing.algorithms, --hashes CHOICE...`: List of hashes to compute for each download *[choices: xxh128, md5, sha256]* *[default: ('xxh128', 'md5', 'sha256')]*
* `--hashing.dedupe.enabled, --dedupe, --dedupe.enabled, --auto-dedupe, --hashing.dedupe.no-enabled, --no-dedupe, --dedupe.no-enabled, --no-auto-dedupe`: Auto delete duplicate downloads by hash *[default: True]*
* `--hashing.dedupe.use-trash-bin, --hashing.dedupe.no-use-trash-bin`: Send deleted files to the trash bin *[default: True]*

**Jdownloader**:

* `--jdownloader.enabled, --jdownloader, --jdownloader.no-enabled, --no-jdownloader`: Send unsupported URLs to Jdownloader *[default: False]*
* `--jdownloader.deprecated-api URL`: HTTP URL of a local JDownloader instance to connect to via their deprecated API (insecure, default port=3128)
* `--jdownloader.autostart, --jdownloader.no-autostart`: Immediately start downloads as soon as they are sent *[default: False]*
* `--jdownloader.download-folder PATH`: Output path for Jdownloader. Defaults to `--download-folder`
* `--jdownloader.whitelist STR...`: Only send unsupported URLs from these domains to Jdownloader. An empty list means 'send all URLs' *[default: {}]*

**Logs**:

* `--logs.level CHOICE`: Only log messages of this level or higher to the main log file *[choices: DEBUG, INFO, WARNING, ERROR, CRITICAL]* *[default: DEBUG]*
* `--logs.console-level CHOICE`: Only log messages of this level or higher to the console. An empty or `None` value will use the same level as `log_level` *[choices: DEBUG, INFO, WARNING, ERROR, CRITICAL]*
* `--logs.http-traffic, --print-traffic, --logs.no-http-traffic, --no-print-traffic`: Log HTTP requests and responses (at INFO level) *[default: True]*
* `--logs.files.main, --log-file PATH`: Path of main log file *[default: downloader.log]*
* `--logs.files.download-errors PATH`: Save download errors to this file (MUST BE .csv) *[default: download_errors.csv]*
* `--logs.files.scrape-errors PATH`: Save scrape errors to this file (MUST BE .csv) *[default: scrape_errors.csv]*
* `--logs.files.unsupported PATH`: Save unsupported URLs to this file (MUST BE .csv) *[default: unsupported.csv]*
* `--logs.files.last-forum-post PATH`: Save the URL of the last scraped post from each thread to this file (MUST BE .csv) *[default: last_forum_post.csv]*
* `--logs.files.dedupe PATH`: Save every duplicate deleted by the deduper, and the file it matched, to this file (MUST BE .csv) *[default: dedupe.csv]*
* `--logs.folder PATH`: Base folder to prepend to log files paths (if they are not absolute)
* `--logs.expire-after TIMEDELTA`: Delete all log files inside `--logs.folder` if they are older that this
* `--logs.rotate, --logs.no-rotate`: Add current datetime to every log file on each run *[default: False]*
* `--logs.rotate-date-position CHOICE`: *[choices: prefix, suffix]* *[default: suffix]*

**MaxChildren**:

* `--max-children.forum INT`: Do not scrape more that this number of URLs inside a forum thread *[default: 0]*
* `--max-children.forum-post INT`: Do not scrape more that this number of URLs inside an individual a forum post *[default: 0]*
* `--max-children.profile INT`: Do not scrape more that this number of URLs in a profile *[default: 0]*
* `--max-children.album INT`: Do not scrape more that this number of URLs in a album *[default: 0]*

**Network**:

* `--dump-responses, --no-dump-responses`: Save text/HTML/JSON responses to disk (Flaresolverr responses are excluded) *[default: False]*
* `--flaresolverr URL`: HTTP URL of an existing Flaresolverr instance
* `--flaresolverr-use-session, --no-flaresolverr-use-session`: Create a custom session before making any request with Flaresolverr *[default: True]*
* `--flaresolverr-wait INT`: Force Flaresolverr to wait (at least) this number of seconds before returning the results, to allow dynamic content to load *[default: 0]*
* `--flaresolverr-concurrency INT`: Number of concurrent requests to make with Flaresolverr *[default: 1]*
* `--proxy, --http-proxy URL`: HTTP/HTTPS proxy
* `--rate-limit FLOAT`: Max number of requests per second (only used while scraping) *[default: 25.0]*
* `--connection-timeout FLOAT`: *[default: 15]*
* `--read-timeout FLOAT`: *[default: 300]*
* `--ssl-context CHOICE`: *[choices: truststore, certifi, truststore+certifi]* *[default: truststore+certifi]*
* `--verify, --ssl, --no-verify, --no-ssl`: *[default: True]*
* `--tls.min-version CHOICE`: *[choices: 1.2, 1.3]* *[default: 1.2]*
* `--ca-certs PATH...`: *[default: ()]*
* `--user-agent STR`: *[default: Mozilla/5.0 (X11; Linux x86_64; rv:153.0) Gecko/20100101 Firefox/153.0]*
* `--impersonate CHOICE`: Use this target as impersonation for all scrape requests *[choices: chrome, edge, safari, safari_ios, chrome_android, firefox]*

**Sort**:

* `--sort.enabled, --sort, --sort.no-enabled, --no-sort`: Enable/Disable file sorting at the end of a run *[default: False]*
* `--sort.input-folder PATH`: Base folder to scan for files. Default to the same value as `--download-folder`
* `--sort.output-folder PATH`: Output path to place sorted files in *[default: downloads/cyberdrop-dl sorted]*
* `--sort.formats.audio STR`: Format to generate sorted audio file *[default: {sort_dir}/{base_dir}/Audio/{filename}{ext}]*
* `--sort.formats.image STR`: Format to generate sorted image file *[default: {sort_dir}/{base_dir}/Images/{filename}{ext}]*
* `--sort.formats.non-media STR`: Format to generate sorted files of unknown type *[default: {sort_dir}/{base_dir}/Other/{filename}{ext}]*
* `--sort.formats.video STR`: Format to generate sorted video file *[default: {sort_dir}/{base_dir}/Videos/{filename}{ext}]*
* `--sort.formats.incrementer STR`: Format for separator on name collisions *[default:  ({i})]*

**SubFolders**:

* `--subfolders.create, --subfolders, --subfolders.no-create, --no-subfolders`: Enable/disable the creation of nested sub-folders *[default: True]*
* `--subfolders.group-loose-files, --subfolders.no-group-loose-files`: Create a subfolder named 'Loose Files' for individual files not part of any album/thread *[default: True]*
* `--subfolders.include.album-id, --subfolders.include.no-album-id`: *[default: False]*
* `--subfolders.include.thread-id, --subfolders.include.no-thread-id`: *[default: False]*
* `--subfolders.include.domain, --subfolders.include.no-domain`: *[default: True]*
* `--subfolders.separate-posts.format STR`: *[default: {default}]*
* `--subfolders.enabled, --separate-posts, --separate-posts.enabled, --subfolders.no-enabled, --no-separate-posts, --separate-posts.no-enabled`: Create new subfolders for every post on a site *[default: False]*

**UIOptions**:

* `--ui CHOICE`: *[choices: disabled, activity, simple, fullscreen]* *[default: fullscreen]*
* `--portrait, --no-portrait`: force CDL to run with a vertical layout *[default: False]*
* `--refresh-rate FLOAT`: *[default: 10.0]*
* `--stats, --no-stats`: Show stats report at the end of a run *[default: True]*

## cyberdrop-dl database

Commands for managing the database

### cyberdrop-dl database prune

Delete database entries that are no longer useful

**Commands**:

* [`hashes`](#cyberdrop-dl-database-prune-hashes): Delete the hashes of files that no longer exist on disk.

#### cyberdrop-dl database prune hashes

```console
cyberdrop-dl database prune hashes [OPTIONS]
```

Delete the hashes of files that no longer exist on disk.

Only affects the `hash` and `files` tables.

**Parameters**:

* `--dry-run, --no-dry-run`: Report what would be deleted without modifying the database *[default: False]*
* `--config-file, --config, -c PATH`: YAML file to use as config
* `--cache-file PATH`: JSON file to use as cache
* `--database-file, --db PATH`: SQLite file to use as database

### cyberdrop-dl database transfer

```console
cyberdrop-dl database transfer [OPTIONS] DATABASE-FILE
```

Migrate an old database to the latest schema version.

**Parameters**:

* `DATABASE-FILE, --database-file`: Path to the SQLite database file to migrate **[required]**
* `--force, --no-force`: Skip the 'already latest' early-exit check and run all migration steps regardless of detected version *[default: False]*

### cyberdrop-dl database file

```console
cyberdrop-dl database file [OPTIONS]
```

Show file path to the database

**Parameters**:

* `--config-file, --config, -c PATH`: YAML file to use as config
* `--cache-file PATH`: JSON file to use as cache
* `--database-file, --db PATH`: SQLite file to use as database

### cyberdrop-dl database dir

```console
cyberdrop-dl database dir [OPTIONS]
```

Open folder with database in default file explorer

**Parameters**:

* `--config-file, --config, -c PATH`: YAML file to use as config
* `--cache-file PATH`: JSON file to use as cache
* `--database-file, --db PATH`: SQLite file to use as database

## cyberdrop-dl cleanup

Perform maintenance tasks

### cyberdrop-dl cleanup files

```console
cyberdrop-dl cleanup files PATH
```

Delete partial (`.cdl_hls` and `.part`) files, empty folders and empty files inside `path` (recursive)

**Arguments**:

* `PATH`: Path of the folder to clean up **[required]**

## cyberdrop-dl config

Config file operations

### cyberdrop-dl config file

```console
cyberdrop-dl config file [OPTIONS]
```

Show path to the config file

**Parameters**:

* `--config-file, --config, -c PATH`: YAML file to use as config
* `--cache-file PATH`: JSON file to use as cache
* `--database-file, --db PATH`: SQLite file to use as database

### cyberdrop-dl config edit

```console
cyberdrop-dl config edit [OPTIONS]
```

Open the default config file on a text editor

**Parameters**:

* `--config-file, --config, -c PATH`: YAML file to use as config
* `--cache-file PATH`: JSON file to use as cache
* `--database-file, --db PATH`: SQLite file to use as database

### cyberdrop-dl config fill

```console
cyberdrop-dl config fill [OPTIONS]
```

Add missing settings to the config file with their default values (comments will be deleted)

Settings from config overrides will be merged into the main config file

**Parameters**:

* `--config-file, --config, -c PATH`: YAML file to use as config
* `--cache-file PATH`: JSON file to use as cache
* `--database-file, --db PATH`: SQLite file to use as database

### cyberdrop-dl config new

```console
cyberdrop-dl config new
```

Create a new config with default options and print it

### cyberdrop-dl config dir

```console
cyberdrop-dl config dir [OPTIONS]
```

Open folder with config file in default file explorer

**Parameters**:

* `--config-file, --config, -c PATH`: YAML file to use as config
* `--cache-file PATH`: JSON file to use as cache
* `--database-file, --db PATH`: SQLite file to use as database

## cyberdrop-dl cache

Cache operations

### cyberdrop-dl cache file

```console
cyberdrop-dl cache file [OPTIONS]
```

Show path to the cache file

**Parameters**:

* `--config-file, --config, -c PATH`: YAML file to use as config
* `--cache-file PATH`: JSON file to use as cache
* `--database-file, --db PATH`: SQLite file to use as database

### cyberdrop-dl cache clear

```console
cyberdrop-dl cache clear [OPTIONS]
```

Delete the cache file

**Parameters**:

* `--config-file, --config, -c PATH`: YAML file to use as config
* `--cache-file PATH`: JSON file to use as cache
* `--database-file, --db PATH`: SQLite file to use as database

### cyberdrop-dl cache dir

```console
cyberdrop-dl cache dir [OPTIONS]
```

Open folder with cache file in default file explorer

**Parameters**:

* `--config-file, --config, -c PATH`: YAML file to use as config
* `--cache-file PATH`: JSON file to use as cache
* `--database-file, --db PATH`: SQLite file to use as database

## cyberdrop-dl retry

Retry downloads from the database

### cyberdrop-dl retry failed

```console
cyberdrop-dl retry failed [OPTIONS]
```

Retry failed downloads

**Parameters**:

* `--from DATE`: Only retry URLs added to the database since this date *[default: 1970-01-01]*
* `--to DATE`: Only retry URLs added to the database before this date *[default: None]*
* `--force-original-path, --no-force-original-path`: Ignore current config options and force downloads to use the exact same path of the initial download attempt *[default: False]*
* `--config-file, --config, -c PATH`: YAML file to use as config
* `--cache-file PATH`: JSON file to use as cache
* `--database-file, --db PATH`: SQLite file to use as database
* `--cookies PATH`: File/folder to import cookies from (.txt Netscape files)
* `--deep-scrape, --no-deep-scrape`: Make additional requests while scraping (slower) *[default: False]*
* `--delete-empty-folders, --no-delete-empty-folders`: Delete empty files and folders after a run *[default: True]*
* `--delete-partial-files, --no-delete-partial-files`: Delete partial files after a run *[default: False]*
* `--download-folder, --output, -o, -d PATH`: Base output path for all downloads *[default: downloads/cyberdrop-dl]*
* `--dump-json, -j, --no-dump-json`: Save details about each file (both skipped and downloaded) to a .jsonl file *[default: False]*
* `--ignore-history, --no-ignore-history`: Download files even if the already are marked as downloaded on the database *[default: False]*
* `--ignore-hashes, --no-ignore-hashes`: Download files even if their hash matches a file downloaded on the database *[default: False]*
* `--max-file-name-length INT`: Max number of characters a filename should have. Filenames longer that this will be truncated *[default: 95]*
* `--max-folder-name-length INT`: Max number of characters a folder should have. Filenames longer that this will be truncated *[default: 60]*
* `--max-thread-depth INT`: Restricts how many levels of nested threads are scraped on a forum *[default: 0]*
* `--max-thread-folder-depth INT`: Max number of nested folders CDL will create when maximum_thread_depth is greater that 0
* `--min-free-space BYTESIZE`: Minimum free space require to start new downloads *[default: 5368709120]*
* `--mtime, --no-mtime`: Use original upload date as modification date for downloaded file *[default: True]*
* `--restrict-path, --restrict-filenames CHOICE...`: *[choices: unix, windows, no_emoji, ascii]* *[default: ()]*
* `--update-check, -U, --no-update-check`: Check for updates at the end of the session *[default: True]*

**Crawlers**:

* `--crawlers.disabled STR...`: Name of crawlers to disable for the current run *[default: {}]*
* `--crawlers.bandcamp.formats CHOICE...`: Format to choose for downloads (if available), ordered by preference *[choices: mp3-320, mp3, aac-hi, wav, flac, vorbis, aiff, alas]* *[default: ('mp3-320', 'mp3', 'aac-hi', 'wav', 'flac', 'vorbis', 'aiff', 'alas')]*
* `--crawlers.bluesky.external, --crawlers.bluesky.no-external`: Parse and download embeds from third-party sites *[default: True]*
* `--crawlers.bluesky.threads, --crawlers.bluesky.no-threads`: Downloads all posts in a thread (All direct replies from OP to their own post) *[default: True]*
* `--crawlers.bluesky.content-urls, --crawlers.bluesky.no-content-urls`: Parse and try to download any URL found inside the text of a post *[default: True]*
* `--crawlers.bluesky.reposts, --crawlers.bluesky.no-reposts`: Download media from reposts in the user's timeline *[default: False]*
* `--crawlers.clonr.use-source, --crawlers.clonr.no-use-source`: Ignore files in clone and process the original Mega.nz URL *[default: False]*
* `--crawlers.clonr.zip, --crawlers.clonr.no-zip`: Download entire clone as a single ZIP file *[default: False]*
* `--crawlers.clypit.prefer-mp3, --crawlers.clypit.no-prefer-mp3`: Download audios as .mp3 files even if WAV (high quality) versions are available *[default: False]*
* `--crawlers.generic.wordpress-media URL...`: *[default: ()]*
* `--crawlers.generic.wordpress-html URL...`: *[default: ()]*
* `--crawlers.generic.discourse URL...`: *[default: ()]*
* `--crawlers.generic.chevereto URL...`: *[default: ()]*
* `--crawlers.generic.kvs URL...`: *[default: ()]*
* `--crawlers.generic.video URL...`: *[default: ()]*
* `--crawlers.generic.peertube URL...`: *[default: ()]*
* `--crawlers.generic.patreon URL...`: *[default: ()]*
* `--crawlers.google-drive.default-formats.docs CHOICE`: Default format for documents (can be overridden per URL with the 'format' query param) *[choices: docx, odt, rtf, txt, epub, pdf, md, zip]* *[default: docx]*
* `--crawlers.google-drive.default-formats.sheets CHOICE`: Default format for spreedsheets (can be overridden per URL with the 'format' query param) *[choices: xlsx, ods, html, csv, tsv]* *[default: xlsx]*
* `--crawlers.google-drive.default-formats.slides CHOICE`: Default format for presentations (can be overridden per URL with the 'format' query param) *[choices: pptx, odp]* *[default: pptx]*
* `--crawlers.octave-music.quality CHOICE`: Quality of audio file to download (lossless are .flac files) *[choices: lossless, mp3-320]* *[default: mp3-320]*
* `--crawlers.octave-music.filename-format STR`: Format to generate audio file *[default: {artist} - {title}{ext}]*
* `--crawlers.one-pace.prefer-dub, --crawlers.one-pace.no-prefer-dub`: Download episodes with english audio tracks instead of japanese (if available) *[default: False]*
* `--crawlers.only-haven.file, --crawlers.only-haven.no-file`: Download the main file in a post (if any) *[default: True]*
* `--crawlers.only-haven.attachments, --crawlers.only-haven.no-attachments`: Download all attachments in a post (may or may not include `file`) *[default: True]*
* `--crawlers.only-haven.content-urls, --crawlers.only-haven.no-content-urls`: Download any URL found inside the description (text) of a post *[default: True]*
* `--crawlers.only-haven.expand-posts, --crawlers.only-haven.no-expand-posts`: Make an additional API request for each post to get original filenames and the content/text (slower) *[default: False]*
* `--crawlers.only-haven.embed, --crawlers.only-haven.no-embed`: Download the embedded file from third party sites (if any)(mega.nz, pcloud, dropbox, etc..) *[default: True]*
* `--crawlers.patreon.content-urls, --crawlers.patreon.no-content-urls`: Download any URL found inside the description (text) of a post *[default: True]*
* `--crawlers.pawchive.file, --crawlers.pawchive.no-file`: Download the main file in a post (if any) *[default: True]*
* `--crawlers.pawchive.attachments, --crawlers.pawchive.no-attachments`: Download all attachments in a post (may or may not include `file`) *[default: True]*
* `--crawlers.pawchive.content-urls, --crawlers.pawchive.no-content-urls`: Download any URL found inside the description (text) of a post *[default: True]*
* `--crawlers.pawchive.expand-posts, --crawlers.pawchive.no-expand-posts`: Make an additional API request for each post to get original filenames and the content/text (slower) *[default: False]*
* `--crawlers.pawchive.embed, --crawlers.pawchive.no-embed`: Download the embedded file from third party sites (if any)(mega.nz, pcloud, dropbox, etc..) *[default: True]*
* `--crawlers.pornhub.profile-paths STR...`: Subpaths to scrape when an input URL is a profile's homepage *[default: ('photos/public', 'gifs/public', 'videos', 'videos/upload')]*
* `--crawlers.reddit.api CHOICE`: *[choices: arctic_shift]* *[default: arctic_shift]*
* `--crawlers.reddit.content-urls, --crawlers.reddit.no-content-urls`: Download any URL found inside the description (text) of a post *[default: True]*
* `--crawlers.reddit.crossposts, --crawlers.reddit.no-crossposts`: Download media in crossposts from another subreddit *[default: True]*
* `--crawlers.reddit.video-previews, --crawlers.reddit.no-video-previews`: Download video previews generated by reddit for externally content hosted *[default: False]*
* `--crawlers.tiktok.original, --crawlers.tiktok.no-original`: Download videos in original quality (slower) *[default: False]*
* `--crawlers.twitter.cards, --crawlers.twitter.no-cards`: Parse and download cards in a post (embeds from third-party sites) *[default: True]*
* `--crawlers.twitter.threads, --crawlers.twitter.no-threads`: Downloads all posts in a thread (All direct replies from OP to their own tweet) *[default: True]*
* `--crawlers.twitter.content-urls, --crawlers.twitter.no-content-urls`: Parse and try to download any URL found inside the text of a tweet *[default: True]*
* `--crawlers.twitter.articles.cover, --crawlers.twitter.articles.no-cover`: Download the cover image of articles *[default: True]*
* `--crawlers.twitter.articles.media, --crawlers.twitter.articles.no-media`: Download media files in the body of articles *[default: True]*
* `--crawlers.twitter.retweets, --crawlers.twitter.no-retweets`: Download media from retweets in the user's timeline *[default: False]*
* `--crawlers.twitter.image-size CHOICE`: *[choices: orig, 4096x4096, large, medium, small, thumb]* *[default: orig]*
* `--crawlers.vk.wall-filter CHOICE`: Which posts to download while scraping an user's wall *[choices: all, others, owner]* *[default: all]*

**Downloads**:

* `--downloads INT`: Max number of files to download simultaneously *[default: 15]*
* `--downloads.per-domain INT`: Max number of files to download simultaneously per domain *[default: 5]*
* `--attempts INT`: *[default: 2]*
* `--delay FLOAT`: Number of seconds to wait before starting downloads *[default: 0.0]*
* `--slow-speed BYTESIZE`: Skip downloads if their speed is below this value for more than 10 seconds. Set to 0 to disable *[default: 0]*
* `--speed-limit BYTESIZE`: Max speed rate (in bytes per second) to limit downloads (combined) *[default: 0]*
* `--back-pressure, --no-back-pressure`: Throttle scrape requests if there are too many downloads queued for the same site *[default: True]*
* `--jitter FLOAT`: Wait a random additional number of seconds in between 0 and <jitter> before downloads *[default: 0]*
* `--skip-and-mark-completed, --no-skip-and-mark-completed`: Skip all downloads and mark them as downloaded on the database *[default: False]*
* `--concurrent-segments INT`: Allow up to `<N>` HLS segments to be downloaded concurrently *[default: 10]*

**Filters**:

* `--audio, --no-audio`: Download/skip audio files *[default: True]*
* `--images, --no-images`: Download/skip image files *[default: True]*
* `--videos, --no-videos`: Download/skip videos *[default: True]*
* `--non-media, --no-non-media`: Download/skip non media files (.txt, zip, .rar, etc...) *[default: True]*
* `--thumbnails, --no-thumbnails`: Download/skip thumbnails of media files (if available) *[default: False]*
* `--image.size.min BYTESIZE`:
* `--image.size.max BYTESIZE`:
* `--video.size.min BYTESIZE`:
* `--video.size.max BYTESIZE`:
* `--audio.size.min BYTESIZE`:
* `--audio.size.max BYTESIZE`:
* `--non_media.size.min BYTESIZE`:
* `--non_media.size.max BYTESIZE`:
* `--video.duration.min TIMEDELTA`:
* `--video.duration.max TIMEDELTA`:
* `--audio.duration.min TIMEDELTA`:
* `--audio.duration.max TIMEDELTA`:
* `--before DATE`: Only download files uploaded before this date
* `--after DATE`: Only download files uploaded after this date
* `--filename-regex PATTERN[STR]`: Only download files that match this regex
* `--filename-regex-exclude PATTERN[STR]`: Do NOT download files that match this regex
* `--only-hosts STR...`: Only scrape/download from these domains *[default: {}]*
* `--skip-hosts STR...`: Skip scrape/download from these domains *[default: {}]*
* `--allow-files-with-no-extension, --no-allow-files-with-no-extension`: Download potentially dangerous files that have no extension *[default: False]*

**Hashing**:

* `--hashing CHOICE`: *[choices: off, in-place, post-download]* *[default: in-place]*
* `--hashing.algorithms, --hashes CHOICE...`: List of hashes to compute for each download *[choices: xxh128, md5, sha256]* *[default: ('xxh128', 'md5', 'sha256')]*
* `--hashing.dedupe.enabled, --dedupe, --dedupe.enabled, --auto-dedupe, --hashing.dedupe.no-enabled, --no-dedupe, --dedupe.no-enabled, --no-auto-dedupe`: Auto delete duplicate downloads by hash *[default: True]*
* `--hashing.dedupe.use-trash-bin, --hashing.dedupe.no-use-trash-bin`: Send deleted files to the trash bin *[default: True]*

**Jdownloader**:

* `--jdownloader.enabled, --jdownloader, --jdownloader.no-enabled, --no-jdownloader`: Send unsupported URLs to Jdownloader *[default: False]*
* `--jdownloader.deprecated-api URL`: HTTP URL of a local JDownloader instance to connect to via their deprecated API (insecure, default port=3128)
* `--jdownloader.autostart, --jdownloader.no-autostart`: Immediately start downloads as soon as they are sent *[default: False]*
* `--jdownloader.download-folder PATH`: Output path for Jdownloader. Defaults to `--download-folder`
* `--jdownloader.whitelist STR...`: Only send unsupported URLs from these domains to Jdownloader. An empty list means 'send all URLs' *[default: {}]*

**Logs**:

* `--logs.level CHOICE`: Only log messages of this level or higher to the main log file *[choices: DEBUG, INFO, WARNING, ERROR, CRITICAL]* *[default: DEBUG]*
* `--logs.console-level CHOICE`: Only log messages of this level or higher to the console. An empty or `None` value will use the same level as `log_level` *[choices: DEBUG, INFO, WARNING, ERROR, CRITICAL]*
* `--logs.http-traffic, --print-traffic, --logs.no-http-traffic, --no-print-traffic`: Log HTTP requests and responses (at INFO level) *[default: True]*
* `--logs.files.main, --log-file PATH`: Path of main log file *[default: downloader.log]*
* `--logs.files.download-errors PATH`: Save download errors to this file (MUST BE .csv) *[default: download_errors.csv]*
* `--logs.files.scrape-errors PATH`: Save scrape errors to this file (MUST BE .csv) *[default: scrape_errors.csv]*
* `--logs.files.unsupported PATH`: Save unsupported URLs to this file (MUST BE .csv) *[default: unsupported.csv]*
* `--logs.files.last-forum-post PATH`: Save the URL of the last scraped post from each thread to this file (MUST BE .csv) *[default: last_forum_post.csv]*
* `--logs.files.dedupe PATH`: Save every duplicate deleted by the deduper, and the file it matched, to this file (MUST BE .csv) *[default: dedupe.csv]*
* `--logs.folder PATH`: Base folder to prepend to log files paths (if they are not absolute)
* `--logs.expire-after TIMEDELTA`: Delete all log files inside `--logs.folder` if they are older that this
* `--logs.rotate, --logs.no-rotate`: Add current datetime to every log file on each run *[default: False]*
* `--logs.rotate-date-position CHOICE`: *[choices: prefix, suffix]* *[default: suffix]*

**MaxChildren**:

* `--max-children.forum INT`: Do not scrape more that this number of URLs inside a forum thread *[default: 0]*
* `--max-children.forum-post INT`: Do not scrape more that this number of URLs inside an individual a forum post *[default: 0]*
* `--max-children.profile INT`: Do not scrape more that this number of URLs in a profile *[default: 0]*
* `--max-children.album INT`: Do not scrape more that this number of URLs in a album *[default: 0]*

**Network**:

* `--dump-responses, --no-dump-responses`: Save text/HTML/JSON responses to disk (Flaresolverr responses are excluded) *[default: False]*
* `--flaresolverr URL`: HTTP URL of an existing Flaresolverr instance
* `--flaresolverr-use-session, --no-flaresolverr-use-session`: Create a custom session before making any request with Flaresolverr *[default: True]*
* `--flaresolverr-wait INT`: Force Flaresolverr to wait (at least) this number of seconds before returning the results, to allow dynamic content to load *[default: 0]*
* `--flaresolverr-concurrency INT`: Number of concurrent requests to make with Flaresolverr *[default: 1]*
* `--proxy, --http-proxy URL`: HTTP/HTTPS proxy
* `--rate-limit FLOAT`: Max number of requests per second (only used while scraping) *[default: 25.0]*
* `--connection-timeout FLOAT`: *[default: 15]*
* `--read-timeout FLOAT`: *[default: 300]*
* `--ssl-context CHOICE`: *[choices: truststore, certifi, truststore+certifi]* *[default: truststore+certifi]*
* `--verify, --ssl, --no-verify, --no-ssl`: *[default: True]*
* `--tls.min-version CHOICE`: *[choices: 1.2, 1.3]* *[default: 1.2]*
* `--ca-certs PATH...`: *[default: ()]*
* `--user-agent STR`: *[default: Mozilla/5.0 (X11; Linux x86_64; rv:153.0) Gecko/20100101 Firefox/153.0]*
* `--impersonate CHOICE`: Use this target as impersonation for all scrape requests *[choices: chrome, edge, safari, safari_ios, chrome_android, firefox]*

**Sort**:

* `--sort.enabled, --sort, --sort.no-enabled, --no-sort`: Enable/Disable file sorting at the end of a run *[default: False]*
* `--sort.input-folder PATH`: Base folder to scan for files. Default to the same value as `--download-folder`
* `--sort.output-folder PATH`: Output path to place sorted files in *[default: downloads/cyberdrop-dl sorted]*
* `--sort.formats.audio STR`: Format to generate sorted audio file *[default: {sort_dir}/{base_dir}/Audio/{filename}{ext}]*
* `--sort.formats.image STR`: Format to generate sorted image file *[default: {sort_dir}/{base_dir}/Images/{filename}{ext}]*
* `--sort.formats.non-media STR`: Format to generate sorted files of unknown type *[default: {sort_dir}/{base_dir}/Other/{filename}{ext}]*
* `--sort.formats.video STR`: Format to generate sorted video file *[default: {sort_dir}/{base_dir}/Videos/{filename}{ext}]*
* `--sort.formats.incrementer STR`: Format for separator on name collisions *[default:  ({i})]*

**SubFolders**:

* `--subfolders.create, --subfolders, --subfolders.no-create, --no-subfolders`: Enable/disable the creation of nested sub-folders *[default: True]*
* `--subfolders.group-loose-files, --subfolders.no-group-loose-files`: Create a subfolder named 'Loose Files' for individual files not part of any album/thread *[default: True]*
* `--subfolders.include.album-id, --subfolders.include.no-album-id`: *[default: False]*
* `--subfolders.include.thread-id, --subfolders.include.no-thread-id`: *[default: False]*
* `--subfolders.include.domain, --subfolders.include.no-domain`: *[default: True]*
* `--subfolders.separate-posts.format STR`: *[default: {default}]*
* `--subfolders.enabled, --separate-posts, --separate-posts.enabled, --subfolders.no-enabled, --no-separate-posts, --separate-posts.no-enabled`: Create new subfolders for every post on a site *[default: False]*

**UIOptions**:

* `--ui CHOICE`: *[choices: disabled, activity, simple, fullscreen]* *[default: fullscreen]*
* `--portrait, --no-portrait`: force CDL to run with a vertical layout *[default: False]*
* `--refresh-rate FLOAT`: *[default: 10.0]*
* `--stats, --no-stats`: Show stats report at the end of a run *[default: True]*

### cyberdrop-dl retry all

```console
cyberdrop-dl retry all [OPTIONS]
```

Retry all downloads

**Parameters**:

* `--from DATE`: Only retry URLs added to the database since this date *[default: 1970-01-01]*
* `--to DATE`: Only retry URLs added to the database before this date *[default: None]*
* `--force-original-path, --no-force-original-path`: Ignore current config options and force downloads to use the exact same path of the initial download attempt *[default: False]*
* `--config-file, --config, -c PATH`: YAML file to use as config
* `--cache-file PATH`: JSON file to use as cache
* `--database-file, --db PATH`: SQLite file to use as database
* `--cookies PATH`: File/folder to import cookies from (.txt Netscape files)
* `--deep-scrape, --no-deep-scrape`: Make additional requests while scraping (slower) *[default: False]*
* `--delete-empty-folders, --no-delete-empty-folders`: Delete empty files and folders after a run *[default: True]*
* `--delete-partial-files, --no-delete-partial-files`: Delete partial files after a run *[default: False]*
* `--download-folder, --output, -o, -d PATH`: Base output path for all downloads *[default: downloads/cyberdrop-dl]*
* `--dump-json, -j, --no-dump-json`: Save details about each file (both skipped and downloaded) to a .jsonl file *[default: False]*
* `--ignore-history, --no-ignore-history`: Download files even if the already are marked as downloaded on the database *[default: False]*
* `--ignore-hashes, --no-ignore-hashes`: Download files even if their hash matches a file downloaded on the database *[default: False]*
* `--max-file-name-length INT`: Max number of characters a filename should have. Filenames longer that this will be truncated *[default: 95]*
* `--max-folder-name-length INT`: Max number of characters a folder should have. Filenames longer that this will be truncated *[default: 60]*
* `--max-thread-depth INT`: Restricts how many levels of nested threads are scraped on a forum *[default: 0]*
* `--max-thread-folder-depth INT`: Max number of nested folders CDL will create when maximum_thread_depth is greater that 0
* `--min-free-space BYTESIZE`: Minimum free space require to start new downloads *[default: 5368709120]*
* `--mtime, --no-mtime`: Use original upload date as modification date for downloaded file *[default: True]*
* `--restrict-path, --restrict-filenames CHOICE...`: *[choices: unix, windows, no_emoji, ascii]* *[default: ()]*
* `--update-check, -U, --no-update-check`: Check for updates at the end of the session *[default: True]*

**Crawlers**:

* `--crawlers.disabled STR...`: Name of crawlers to disable for the current run *[default: {}]*
* `--crawlers.bandcamp.formats CHOICE...`: Format to choose for downloads (if available), ordered by preference *[choices: mp3-320, mp3, aac-hi, wav, flac, vorbis, aiff, alas]* *[default: ('mp3-320', 'mp3', 'aac-hi', 'wav', 'flac', 'vorbis', 'aiff', 'alas')]*
* `--crawlers.bluesky.external, --crawlers.bluesky.no-external`: Parse and download embeds from third-party sites *[default: True]*
* `--crawlers.bluesky.threads, --crawlers.bluesky.no-threads`: Downloads all posts in a thread (All direct replies from OP to their own post) *[default: True]*
* `--crawlers.bluesky.content-urls, --crawlers.bluesky.no-content-urls`: Parse and try to download any URL found inside the text of a post *[default: True]*
* `--crawlers.bluesky.reposts, --crawlers.bluesky.no-reposts`: Download media from reposts in the user's timeline *[default: False]*
* `--crawlers.clonr.use-source, --crawlers.clonr.no-use-source`: Ignore files in clone and process the original Mega.nz URL *[default: False]*
* `--crawlers.clonr.zip, --crawlers.clonr.no-zip`: Download entire clone as a single ZIP file *[default: False]*
* `--crawlers.clypit.prefer-mp3, --crawlers.clypit.no-prefer-mp3`: Download audios as .mp3 files even if WAV (high quality) versions are available *[default: False]*
* `--crawlers.generic.wordpress-media URL...`: *[default: ()]*
* `--crawlers.generic.wordpress-html URL...`: *[default: ()]*
* `--crawlers.generic.discourse URL...`: *[default: ()]*
* `--crawlers.generic.chevereto URL...`: *[default: ()]*
* `--crawlers.generic.kvs URL...`: *[default: ()]*
* `--crawlers.generic.video URL...`: *[default: ()]*
* `--crawlers.generic.peertube URL...`: *[default: ()]*
* `--crawlers.generic.patreon URL...`: *[default: ()]*
* `--crawlers.google-drive.default-formats.docs CHOICE`: Default format for documents (can be overridden per URL with the 'format' query param) *[choices: docx, odt, rtf, txt, epub, pdf, md, zip]* *[default: docx]*
* `--crawlers.google-drive.default-formats.sheets CHOICE`: Default format for spreedsheets (can be overridden per URL with the 'format' query param) *[choices: xlsx, ods, html, csv, tsv]* *[default: xlsx]*
* `--crawlers.google-drive.default-formats.slides CHOICE`: Default format for presentations (can be overridden per URL with the 'format' query param) *[choices: pptx, odp]* *[default: pptx]*
* `--crawlers.octave-music.quality CHOICE`: Quality of audio file to download (lossless are .flac files) *[choices: lossless, mp3-320]* *[default: mp3-320]*
* `--crawlers.octave-music.filename-format STR`: Format to generate audio file *[default: {artist} - {title}{ext}]*
* `--crawlers.one-pace.prefer-dub, --crawlers.one-pace.no-prefer-dub`: Download episodes with english audio tracks instead of japanese (if available) *[default: False]*
* `--crawlers.only-haven.file, --crawlers.only-haven.no-file`: Download the main file in a post (if any) *[default: True]*
* `--crawlers.only-haven.attachments, --crawlers.only-haven.no-attachments`: Download all attachments in a post (may or may not include `file`) *[default: True]*
* `--crawlers.only-haven.content-urls, --crawlers.only-haven.no-content-urls`: Download any URL found inside the description (text) of a post *[default: True]*
* `--crawlers.only-haven.expand-posts, --crawlers.only-haven.no-expand-posts`: Make an additional API request for each post to get original filenames and the content/text (slower) *[default: False]*
* `--crawlers.only-haven.embed, --crawlers.only-haven.no-embed`: Download the embedded file from third party sites (if any)(mega.nz, pcloud, dropbox, etc..) *[default: True]*
* `--crawlers.patreon.content-urls, --crawlers.patreon.no-content-urls`: Download any URL found inside the description (text) of a post *[default: True]*
* `--crawlers.pawchive.file, --crawlers.pawchive.no-file`: Download the main file in a post (if any) *[default: True]*
* `--crawlers.pawchive.attachments, --crawlers.pawchive.no-attachments`: Download all attachments in a post (may or may not include `file`) *[default: True]*
* `--crawlers.pawchive.content-urls, --crawlers.pawchive.no-content-urls`: Download any URL found inside the description (text) of a post *[default: True]*
* `--crawlers.pawchive.expand-posts, --crawlers.pawchive.no-expand-posts`: Make an additional API request for each post to get original filenames and the content/text (slower) *[default: False]*
* `--crawlers.pawchive.embed, --crawlers.pawchive.no-embed`: Download the embedded file from third party sites (if any)(mega.nz, pcloud, dropbox, etc..) *[default: True]*
* `--crawlers.pornhub.profile-paths STR...`: Subpaths to scrape when an input URL is a profile's homepage *[default: ('photos/public', 'gifs/public', 'videos', 'videos/upload')]*
* `--crawlers.reddit.api CHOICE`: *[choices: arctic_shift]* *[default: arctic_shift]*
* `--crawlers.reddit.content-urls, --crawlers.reddit.no-content-urls`: Download any URL found inside the description (text) of a post *[default: True]*
* `--crawlers.reddit.crossposts, --crawlers.reddit.no-crossposts`: Download media in crossposts from another subreddit *[default: True]*
* `--crawlers.reddit.video-previews, --crawlers.reddit.no-video-previews`: Download video previews generated by reddit for externally content hosted *[default: False]*
* `--crawlers.tiktok.original, --crawlers.tiktok.no-original`: Download videos in original quality (slower) *[default: False]*
* `--crawlers.twitter.cards, --crawlers.twitter.no-cards`: Parse and download cards in a post (embeds from third-party sites) *[default: True]*
* `--crawlers.twitter.threads, --crawlers.twitter.no-threads`: Downloads all posts in a thread (All direct replies from OP to their own tweet) *[default: True]*
* `--crawlers.twitter.content-urls, --crawlers.twitter.no-content-urls`: Parse and try to download any URL found inside the text of a tweet *[default: True]*
* `--crawlers.twitter.articles.cover, --crawlers.twitter.articles.no-cover`: Download the cover image of articles *[default: True]*
* `--crawlers.twitter.articles.media, --crawlers.twitter.articles.no-media`: Download media files in the body of articles *[default: True]*
* `--crawlers.twitter.retweets, --crawlers.twitter.no-retweets`: Download media from retweets in the user's timeline *[default: False]*
* `--crawlers.twitter.image-size CHOICE`: *[choices: orig, 4096x4096, large, medium, small, thumb]* *[default: orig]*
* `--crawlers.vk.wall-filter CHOICE`: Which posts to download while scraping an user's wall *[choices: all, others, owner]* *[default: all]*

**Downloads**:

* `--downloads INT`: Max number of files to download simultaneously *[default: 15]*
* `--downloads.per-domain INT`: Max number of files to download simultaneously per domain *[default: 5]*
* `--attempts INT`: *[default: 2]*
* `--delay FLOAT`: Number of seconds to wait before starting downloads *[default: 0.0]*
* `--slow-speed BYTESIZE`: Skip downloads if their speed is below this value for more than 10 seconds. Set to 0 to disable *[default: 0]*
* `--speed-limit BYTESIZE`: Max speed rate (in bytes per second) to limit downloads (combined) *[default: 0]*
* `--back-pressure, --no-back-pressure`: Throttle scrape requests if there are too many downloads queued for the same site *[default: True]*
* `--jitter FLOAT`: Wait a random additional number of seconds in between 0 and <jitter> before downloads *[default: 0]*
* `--skip-and-mark-completed, --no-skip-and-mark-completed`: Skip all downloads and mark them as downloaded on the database *[default: False]*
* `--concurrent-segments INT`: Allow up to `<N>` HLS segments to be downloaded concurrently *[default: 10]*

**Filters**:

* `--audio, --no-audio`: Download/skip audio files *[default: True]*
* `--images, --no-images`: Download/skip image files *[default: True]*
* `--videos, --no-videos`: Download/skip videos *[default: True]*
* `--non-media, --no-non-media`: Download/skip non media files (.txt, zip, .rar, etc...) *[default: True]*
* `--thumbnails, --no-thumbnails`: Download/skip thumbnails of media files (if available) *[default: False]*
* `--image.size.min BYTESIZE`:
* `--image.size.max BYTESIZE`:
* `--video.size.min BYTESIZE`:
* `--video.size.max BYTESIZE`:
* `--audio.size.min BYTESIZE`:
* `--audio.size.max BYTESIZE`:
* `--non_media.size.min BYTESIZE`:
* `--non_media.size.max BYTESIZE`:
* `--video.duration.min TIMEDELTA`:
* `--video.duration.max TIMEDELTA`:
* `--audio.duration.min TIMEDELTA`:
* `--audio.duration.max TIMEDELTA`:
* `--before DATE`: Only download files uploaded before this date
* `--after DATE`: Only download files uploaded after this date
* `--filename-regex PATTERN[STR]`: Only download files that match this regex
* `--filename-regex-exclude PATTERN[STR]`: Do NOT download files that match this regex
* `--only-hosts STR...`: Only scrape/download from these domains *[default: {}]*
* `--skip-hosts STR...`: Skip scrape/download from these domains *[default: {}]*
* `--allow-files-with-no-extension, --no-allow-files-with-no-extension`: Download potentially dangerous files that have no extension *[default: False]*

**Hashing**:

* `--hashing CHOICE`: *[choices: off, in-place, post-download]* *[default: in-place]*
* `--hashing.algorithms, --hashes CHOICE...`: List of hashes to compute for each download *[choices: xxh128, md5, sha256]* *[default: ('xxh128', 'md5', 'sha256')]*
* `--hashing.dedupe.enabled, --dedupe, --dedupe.enabled, --auto-dedupe, --hashing.dedupe.no-enabled, --no-dedupe, --dedupe.no-enabled, --no-auto-dedupe`: Auto delete duplicate downloads by hash *[default: True]*
* `--hashing.dedupe.use-trash-bin, --hashing.dedupe.no-use-trash-bin`: Send deleted files to the trash bin *[default: True]*

**Jdownloader**:

* `--jdownloader.enabled, --jdownloader, --jdownloader.no-enabled, --no-jdownloader`: Send unsupported URLs to Jdownloader *[default: False]*
* `--jdownloader.deprecated-api URL`: HTTP URL of a local JDownloader instance to connect to via their deprecated API (insecure, default port=3128)
* `--jdownloader.autostart, --jdownloader.no-autostart`: Immediately start downloads as soon as they are sent *[default: False]*
* `--jdownloader.download-folder PATH`: Output path for Jdownloader. Defaults to `--download-folder`
* `--jdownloader.whitelist STR...`: Only send unsupported URLs from these domains to Jdownloader. An empty list means 'send all URLs' *[default: {}]*

**Logs**:

* `--logs.level CHOICE`: Only log messages of this level or higher to the main log file *[choices: DEBUG, INFO, WARNING, ERROR, CRITICAL]* *[default: DEBUG]*
* `--logs.console-level CHOICE`: Only log messages of this level or higher to the console. An empty or `None` value will use the same level as `log_level` *[choices: DEBUG, INFO, WARNING, ERROR, CRITICAL]*
* `--logs.http-traffic, --print-traffic, --logs.no-http-traffic, --no-print-traffic`: Log HTTP requests and responses (at INFO level) *[default: True]*
* `--logs.files.main, --log-file PATH`: Path of main log file *[default: downloader.log]*
* `--logs.files.download-errors PATH`: Save download errors to this file (MUST BE .csv) *[default: download_errors.csv]*
* `--logs.files.scrape-errors PATH`: Save scrape errors to this file (MUST BE .csv) *[default: scrape_errors.csv]*
* `--logs.files.unsupported PATH`: Save unsupported URLs to this file (MUST BE .csv) *[default: unsupported.csv]*
* `--logs.files.last-forum-post PATH`: Save the URL of the last scraped post from each thread to this file (MUST BE .csv) *[default: last_forum_post.csv]*
* `--logs.files.dedupe PATH`: Save every duplicate deleted by the deduper, and the file it matched, to this file (MUST BE .csv) *[default: dedupe.csv]*
* `--logs.folder PATH`: Base folder to prepend to log files paths (if they are not absolute)
* `--logs.expire-after TIMEDELTA`: Delete all log files inside `--logs.folder` if they are older that this
* `--logs.rotate, --logs.no-rotate`: Add current datetime to every log file on each run *[default: False]*
* `--logs.rotate-date-position CHOICE`: *[choices: prefix, suffix]* *[default: suffix]*

**MaxChildren**:

* `--max-children.forum INT`: Do not scrape more that this number of URLs inside a forum thread *[default: 0]*
* `--max-children.forum-post INT`: Do not scrape more that this number of URLs inside an individual a forum post *[default: 0]*
* `--max-children.profile INT`: Do not scrape more that this number of URLs in a profile *[default: 0]*
* `--max-children.album INT`: Do not scrape more that this number of URLs in a album *[default: 0]*

**Network**:

* `--dump-responses, --no-dump-responses`: Save text/HTML/JSON responses to disk (Flaresolverr responses are excluded) *[default: False]*
* `--flaresolverr URL`: HTTP URL of an existing Flaresolverr instance
* `--flaresolverr-use-session, --no-flaresolverr-use-session`: Create a custom session before making any request with Flaresolverr *[default: True]*
* `--flaresolverr-wait INT`: Force Flaresolverr to wait (at least) this number of seconds before returning the results, to allow dynamic content to load *[default: 0]*
* `--flaresolverr-concurrency INT`: Number of concurrent requests to make with Flaresolverr *[default: 1]*
* `--proxy, --http-proxy URL`: HTTP/HTTPS proxy
* `--rate-limit FLOAT`: Max number of requests per second (only used while scraping) *[default: 25.0]*
* `--connection-timeout FLOAT`: *[default: 15]*
* `--read-timeout FLOAT`: *[default: 300]*
* `--ssl-context CHOICE`: *[choices: truststore, certifi, truststore+certifi]* *[default: truststore+certifi]*
* `--verify, --ssl, --no-verify, --no-ssl`: *[default: True]*
* `--tls.min-version CHOICE`: *[choices: 1.2, 1.3]* *[default: 1.2]*
* `--ca-certs PATH...`: *[default: ()]*
* `--user-agent STR`: *[default: Mozilla/5.0 (X11; Linux x86_64; rv:153.0) Gecko/20100101 Firefox/153.0]*
* `--impersonate CHOICE`: Use this target as impersonation for all scrape requests *[choices: chrome, edge, safari, safari_ios, chrome_android, firefox]*

**Sort**:

* `--sort.enabled, --sort, --sort.no-enabled, --no-sort`: Enable/Disable file sorting at the end of a run *[default: False]*
* `--sort.input-folder PATH`: Base folder to scan for files. Default to the same value as `--download-folder`
* `--sort.output-folder PATH`: Output path to place sorted files in *[default: downloads/cyberdrop-dl sorted]*
* `--sort.formats.audio STR`: Format to generate sorted audio file *[default: {sort_dir}/{base_dir}/Audio/{filename}{ext}]*
* `--sort.formats.image STR`: Format to generate sorted image file *[default: {sort_dir}/{base_dir}/Images/{filename}{ext}]*
* `--sort.formats.non-media STR`: Format to generate sorted files of unknown type *[default: {sort_dir}/{base_dir}/Other/{filename}{ext}]*
* `--sort.formats.video STR`: Format to generate sorted video file *[default: {sort_dir}/{base_dir}/Videos/{filename}{ext}]*
* `--sort.formats.incrementer STR`: Format for separator on name collisions *[default:  ({i})]*

**SubFolders**:

* `--subfolders.create, --subfolders, --subfolders.no-create, --no-subfolders`: Enable/disable the creation of nested sub-folders *[default: True]*
* `--subfolders.group-loose-files, --subfolders.no-group-loose-files`: Create a subfolder named 'Loose Files' for individual files not part of any album/thread *[default: True]*
* `--subfolders.include.album-id, --subfolders.include.no-album-id`: *[default: False]*
* `--subfolders.include.thread-id, --subfolders.include.no-thread-id`: *[default: False]*
* `--subfolders.include.domain, --subfolders.include.no-domain`: *[default: True]*
* `--subfolders.separate-posts.format STR`: *[default: {default}]*
* `--subfolders.enabled, --separate-posts, --separate-posts.enabled, --subfolders.no-enabled, --no-separate-posts, --separate-posts.no-enabled`: Create new subfolders for every post on a site *[default: False]*

**UIOptions**:

* `--ui CHOICE`: *[choices: disabled, activity, simple, fullscreen]* *[default: fullscreen]*
* `--portrait, --no-portrait`: force CDL to run with a vertical layout *[default: False]*
* `--refresh-rate FLOAT`: *[default: 10.0]*
* `--stats, --no-stats`: Show stats report at the end of a run *[default: True]*

## cyberdrop-dl hash

```console
cyberdrop-dl hash [OPTIONS] FOLDER
```

Compute and save hashes of every file in a folder (recursively)

**Arguments**:

* `FOLDER`: **[required]**

**Parameters**:

* `--hashes CHOICE...`: *[choices: xxh128, md5, sha256]*
* `--config-file, --config, -c PATH`: YAML file to use as config
* `--cache-file PATH`: JSON file to use as cache
* `--database-file, --db PATH`: SQLite file to use as database

## cyberdrop-dl docs

```console
cyberdrop-dl docs [OPTIONS]
```

Show documentation for every command

**Parameters**:

* `--format CHOICE`: *[choices: markdown, md, html, htm, rst, rest]* *[default: markdown]*
