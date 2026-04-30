# INSTALL

## Software to install on Windows

1. PostgreSQL
   Use the same PostgreSQL major version as the source machine if you want the
   fastest physical restore path. Portable restore can tolerate the same major
   version or newer.

2. Python 3.10+
   Install Python and enable the option that adds `python` / `py` to PATH.

3. Python package

```powershell
cd C:\path\to\pg_portable_backup
py -3 -m pip install -r requirements.txt
```

4. Google Drive transport
   Choose one:
   * Google Drive for Desktop
   * rclone

## First pack

```powershell
cd C:\path\to\pg_portable_backup
py -3 backup.py --config config.codex.json --dry-run
```

If `local_cluster` is configured, the tool briefly stops the local PostgreSQL
cluster, copies the data directory for fast recovery, then starts the cluster
again.

For the guided version, run:

```powershell
cd C:\path\to\pg_portable_backup
.\run_pack.bat
```

## First unpack

Copy `secrets\env_key.bin` from the source machine or its secure backup before
running restore.

For the guided version, run:

```powershell
cd C:\path\to\pg_portable_backup
.\run_unpack.bat
```

For direct CLI use:

```powershell
py -3 restore.py --config config.codex.json --install latest --restore-mode auto
```
