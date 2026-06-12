# pg_portable_backup

Combined backup and restore home for the local PostgreSQL systems plus their
code trees, aimed at a Windows operator workflow with Google Drive storage.

The default backup entry point now runs both configured systems:

* Codex/OFBiz local: `ofbiz_world_local` plus the Codex scripts tree.
* RCSi ERP: `rcsidatabase` plus the RCSi Catalog Export and ERP script trees.
* Thuraya Prepay Airtime: the OneDrive Thuraya application package.
* Local Documents code: the local `C:\Users\PASCA\Documents` code tree.
* OneDrive Scripts Code: the full `C:\Users\PASCA\OneDrive\Documents\Scripts` project tree.

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

Use `run_backup.bat` to run the combined backup with a visible progress window.
The weekly scheduled task uses the same launcher with `--no-pause`, so progress
is visible while the task is running and the window can close when finished.
`backup_all.py` uses `.backup_all.lock` to prevent duplicate runs if an older
scheduled task wakes up at the same time.

Use `backup_all.py --dry-run` to run the same combined workflow without remote
upload/prune.

Use `run_pack.bat` to open the guided packing page with working buttons for
the Codex/OFBiz job.

Use `run_unpack.bat` to open the guided unpacking page with:

* official download links for PostgreSQL, Python, Google Drive for Desktop,
  and rclone
* archive selection from the configured remote
* buttons for fast restore and portable restore

The HTML pages are served through `portable_backup_server.py`, because plain
browser HTML cannot safely launch local backup scripts by itself.

## CLI examples

```powershell
# dry-run combined pack
py -3 backup_all.py --dry-run

# full combined pack
py -3 backup_all.py

# dry-run one pack
py -3 backup.py --config config.codex.logical.json --dry-run
py -3 backup.py --config config.rcsi.json --dry-run

# full one pack
py -3 backup.py --config config.codex.logical.json
py -3 backup.py --config config.rcsi.json

# list remote archives
py -3 restore.py --config config.codex.json --list

# auto-select restore mode
py -3 restore.py --config config.codex.json --install latest --restore-mode auto
py -3 restore.py --config config.rcsi.json --install latest --restore-mode auto

# force the physical fast path
py -3 restore.py --config config.codex.json --install latest --restore-mode fast

# force the logical portable path
py -3 restore.py --config config.codex.json --install latest --restore-mode portable
```

## Notes

* Fast recovery is meant for the same PostgreSQL major version and a closely
  matching local setup.
* The weekly combined runner uses the logical Codex/OFBiz config so it does
  not stop the live local PostgreSQL cluster for a physical snapshot.
* The weekly combined runner also archives the full OneDrive Scripts tree, so
  individual project folders like QKBK, GDrive_Backup, PC_Audit, and RCSi CDR
  scripts do not need separate scheduled jobs.
* Portable recovery remains the fallback when the target machine differs.
* The archive itself is not fully encrypted; only the configured env/config
  file is encrypted.
