# Telegram Sync

Synchronize Telegram messages and media to local storage.


## Quick Start

1. Clone this repo, configure `docker-compose.yaml`. The following volumes are used by `tgsync`:
    * `/appdata`: Configuration files, session data, and logs
    * `/media`: Downloaded media files
    * `/temp`: Temporary directory for incomplete downloads (MTProto downloads typically cause minimal fragmentation)

2. Start the container in interactive mode to login:
   ```sh
   docker compose up -d postgres
   # Wait for a few seconds for postgres to start
   docker compose run --rm tgsync
   ```

3. Configure the application:
   - Copy `appdata/config.example.json` to `appdata/config.json`
   - Edit `appdata/config.json`

   ```js
   {
     "log": {
       "level": "INFO",
       "dir": null
     },
     "db": {
       "url": "postgresql+psycopg2://tgsync:tgsync@postgres:5432/tgsync"
     },
     "tg": {
       "api_id": -1,   // See:
       "api_hash": "", // https://core.telegram.org/api/obtaining_api_id
       "session": "/appdata/tgsync-default.session",
       "message_limit": 2000, // Number of messages to fetch in one request
       "concurrent_downloads": 4, // Maximum number of concurrent media downloads
       "progress_summary_interval": 30, // Interval in seconds to log progress summary
        "chats": {
          "-10023333333": {}, // Key: Chat ID to sync, available at `/appdata/chats.json` after first login
          "-10066666666": {
            "range": [500, 0] // Sync range, 0 means no limit on that side, leave empty to sync all messages
          }
        }
     }
   }
   ```

4. Start services:
   ```sh
   docker compose up -d
   ```


## Media Storage Structure

The application implements an efficient storage system for media files:

1. Original media files are stored in corresponding repos, `/media/{photo,documents}-by-id/`, with name `<media_id>.ext`
2. Hard links are created to `/media/<chat_id>/` with name `<msg_id>_<photo_id>.ext` or `<msg_id> <original_filename>.ext`
for any message containing that media

This ensures that duplicate media files are not downloaded multiple times, and no additional space is used while each
chat maintains its own organized media directory.


#### Managing Media Files

To delete a specific media file from repo and all chat dirs:
```sh
find /media -samefile "<awful_media_from_repo_or_chat_dir>" -delete
```

To clean up orphaned media files (those no longer referenced by any chat) in repos:
```sh
find /media/{photo,documents}-by-id/ -links 1 -delete
```

**NOTE**: Once a media file is deleted from the repo, it will not be re-downloaded even when referenced by new messages.

For more information about hard links, visit [Wikipedia](https://en.wikipedia.org/wiki/Hard_link).
