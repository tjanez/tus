Manual steps for testing `tus-partclone` command
================================================

### Create a new virtualenv and install `tus`:

```
mkvirtualenv --python=python3 tus
pip install <path-to-tus-directory>
```

### Then set and export the variables that specify the source device to backup,
backup directory and the destination device where to perform the restore:

```
export TUS_SOURCE_DEV=<a-partition-of-suitable-size>
export TUS_BACKUP_DIR=<path-to-backup-directory>
export TUS_BACKUP_FILE=<path-to-one-of-the-backed-up-files>
export TUS_DEST_DEV=<an-empty-device-for-restore>
```

### Create a backup with:

```
sudo ~/.virtualenvs/tus/bin/tus-partclone backup \
    --backup-dir "${TUS_BACKUP_DIR}" --archive-size 100 \
    "${TUS_SOURCE_DEV}"
```

### Restore the backup with:

```
sudo ~/.virtualenvs/tus/bin/tus-partclone restore \
    "--log-file=${TUS_BACKUP_DIR}/tus-restore.log" \
    "${TUS_BACKUP_FILE}" "${TUS_DEST_DEV}"
```

### Test if the contents of the partition is the same after restore:

Mount both directories:

```
sudo mkdir -p /mnt/tus-original
sudo mkdir -p /mnt/tus-restored
sudo mount "${TUS_SOURCE_DEV}" /mnt/tus-original
sudo mount "${TUS_DEST_DEV}" /mnt/tus-restored
```

Check that all SHA256SUMs of the files are the same:

```
sudo sha256deep -r /mnt/tus-original > /tmp/tus-original_sha256sums
sudo sha256deep -r -X /tmp/tus-original_sha256sums /mnt/tus-restored
```

Unmount both directories:
```
sudo umount /mnt/tus-original
sudo umount /mnt/tus-restored
```
