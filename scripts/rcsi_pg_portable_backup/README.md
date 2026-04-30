# pg_portable_backup

Portable backup and restore for the RCSi ERP PostgreSQL database plus its code
folders, with Google Drive storage and operator-friendly HTML guides.

## What this version includes

* `backup.py` for pack
* `restore.py` for unpack
* `pack.html` and `unpack.html` with the full detailed procedure
* `portable_backup_server.py` so those HTML pages can also run real jobs
* live status streaming
* unpack dry-run support
* optional fast physical restore support when `local_cluster` is configured

## Operator entry points

Use:

* `run_pack.bat` to open the interactive pack guide
* `run_unpack.bat` to open the interactive unpack guide
* `run_backup.bat` for direct CLI-style backup
* `run_restore.bat` for direct CLI-style restore

The HTML pages are still full step-by-step documents, but now they also have
real buttons and a live status panel when opened through the launcher.

## Direct commands

```powershell
py -3 backup.py --config config.rcsi.json --dry-run
py -3 backup.py --config config.rcsi.json
py -3 restore.py --config config.rcsi.json --list
py -3 restore.py --config config.rcsi.json --install latest --restore-mode auto
py -3 restore.py --config config.rcsi.json --install-file path\to\archive.tar.gz --dry-run
```

## Notes

* If `local_cluster` is not configured, the tool stays in portable logical mode.
* `secrets\env_key.bin` is required to decrypt the archived env/config file.
* The RCSi-specific source folders and database settings remain in `config.rcsi.json`.
