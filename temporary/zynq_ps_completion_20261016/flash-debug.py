from pathlib import Path
for f in ['camera/build/boot/flash-backup-20261016-222354.bin','camera/build/boot/BOOT.bin']:
 d=Path(f).read_bytes();print(f,len(d),d[:64].hex())
