#!/bin/sh
termux-setup-storage
pkg upgrade -y
pkg install rust which micro libjpeg-turbo python uv -y

# Making sure maturin knows we are building ON Android, not FOR Android
ANDROID_API_LEVEL=24
export ANDROID_API_LEVEL

uv tool install --upgrade --force cyberdrop-dl-patched
uv tool update-shell
mkdir /sdcard/cyberdrop-dl
echo 'alias cyberdrop-dl="cyberdrop-dl --appdata-folder /sdcard/cyberdrop-dl"' >> ~/.bashrc
source ~/.bashrc
