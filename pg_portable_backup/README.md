# pg_portable_backup

Backup and restore for a PostgreSQL database plus its code tree, aimed at a
Windows operator workflow with Google Drive storage.

The package now supports two recovery modes inside one archive:

* `fast` recovery: an offline copy of the local PostgreSQL data directory for
  same-machine-version restoration.
* `portable` recovery: `pg_dump` / `pg_restore` artifacts for safer moves to a
  different machine or a newer PostgreSQL install.

## What a backup contains

One `system_<timestamp>.tar.gz` archive with:

```text
manifest.json            metadata + SHA-256 hashes
RESTORE.md               short restore note
database/cluster.dump    pg_dump -Fc logical dump
database/globals.sql     pg_dumpall --globals-only
physical/data/...        fast-recovery PostgreSQL data directory snapshot
physical/metadata.json   snapshot notes
app/<label>/...          configured source files and folders
config/env.enc           encrypted config file
```

The encrypted config cannot be recovered without `secrets/env_key.bin`, so
that key must be kept separately.

## Main files

```text
pg_portable_backup/
├── backup.py
├── restore.py
├── portable_backup_server.py
├── pack.html
├── unpack.html
├── run_pack.bat
├── run_unpack.bat
├── run_backup.bat
├── run_restore.bat
├── config.example.json
├── config.codex.json
├── requirements.txt
└── lib/
```

## Operator flow

Use `run_pack.bat` to open the guided packing page with working buttons.

Use `run_unpack.bat` to open the guided unpacking page with:

* official download links for PostgreSQL, Python, Google Drive for Desktop,
  and rclone
* archive selection from the configured remote
* buttons for fast restore and portable restore

The HTML pages are served through `portable_backup_server.py`, because plain
browser HTML cannot safely launch local backup scripts by itself.

## CLI examples

```powershell
# dry-run pack
py -3 backup.py --config config.codex.json --dry-run

# full pack
py -3 backup.py --config config.codex.json

# list remote archives
py -3 restore.py --config config.codex.json --list

# auto-select restore mode
py -3 restore.py --config config.codex.json --install latest --restore-mode auto

# force the physical fast path
py -3 restore.py --config config.codex.json --install latest --restore-mode fast

# force the logical portable path
py -3 restore.py --config config.codex.json --install latest --restore-mode portable
```

## Notes

* Fast recovery is meant for the same PostgreSQL major version and a closely
  matching local setup.
* Portable recovery remains the fallback when the target machine differs.
* The archive itself is not fully encrypted; only the configured env/config
  file is encrypted.
