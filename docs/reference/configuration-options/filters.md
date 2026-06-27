# Filters

```yaml
filters:
  after: null
  allow_files_with_no_extension: false
  before: null
  duration:
    audio:
      max: 0:00:00
      min: 0:00:00
    video:
      max: 0:00:00
      min: 0:00:00
  filename_regex: null
  files:
    audio: true
    images: true
    non_media: true
    videos: true
  only_hosts: []
  sizes:
    audio:
      max: 0B
      min: 0B
    image:
      max: 0B
      min: 0B
    non_media:
      max: 0B
      min: 0B
    video:
      max: 0B
      min: 0B
  skip_hosts: []
```

```yaml
download_folder: downloads/cyberdrop-dl
dump_json: false

hashing:
  algorithms:
    - xxh128
    - md5
    - sha256
  dedupe:
    enabled: true
    use_trash_bin: true
  mode: in_place
ignore_history: false

max_file_name_length: 95
max_folder_name_length: 60
max_thread_depth: 0
max_thread_folder_depth: null
min_free_space: 5.0GB

notifications:
  apprise: []
  webhook: null
show_stats: true
sort:
  enabled: false
  formats:
    audio: "{sort_dir}/{base_dir}/Audio/{filename}{ext}"
    image: "{sort_dir}/{base_dir}/Images/{filename}{ext}"
    incrementer: " ({i})"
    non_media: "{sort_dir}/{base_dir}/Other/{filename}{ext}"
    video: "{sort_dir}/{base_dir}/Videos/{filename}{ext}"
  input_folder: null
  output_folder: downloads/cyberdrop-dl sorted

ui:
  mode: fullscreen
  portrait: false
  refresh_rate: 10.0
```
