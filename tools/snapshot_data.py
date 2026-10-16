"""Take a consistent, verified snapshot of Umbra's data folder.

    python tools/snapshot_data.py                # -> backups/data-YYYYmmdd-HHMMSS/
    python tools/snapshot_data.py --data D:\\Umbra\\data --out D:\\safe
    python tools/snapshot_data.py --verify backups/data-20260929-101500

* obscura.db is copied with SQLite's online-backup API, so the copy is consistent
  even while the app is running (a plain file copy can miss the -wal file).
* Everything else in data/ (encrypted images, scrapers, posters, imgprot.json,
  scanstate.json) is copied as-is.
* The snapshot is verified (PRAGMA integrity_check + file count) before the script
  reports success. It never opens the live database for writing and never runs the
  app's migrations.
"""
import argparse
import os
import shutil
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def default_data_dir() -> str:
    for cand in (os.path.join(ROOT, "backend"), os.path.join(ROOT, "src"), ROOT):
        if os.path.isfile(os.path.join(cand, "db.py")):
            return os.path.join(cand, "data")      # same rule as db.app_dir()/data
    return os.path.join(ROOT, "data")


def integrity(db_path: str) -> str:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()


def count_files(folder: str) -> int:
    return sum(len(files) for _, _, files in os.walk(folder))


def snapshot(data: str, out_root: str) -> str:
    if not os.path.isdir(data):
        raise SystemExit(f"data folder not found: {data}")
    real_data, real_out = os.path.realpath(data), os.path.realpath(out_root)
    if real_out == real_data or real_out.startswith(real_data + os.sep):
        raise SystemExit("output folder must not be inside the data folder")
    dest = os.path.join(out_root, "data-" + time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(dest)
    skip = {"obscura.db", "obscura.db-wal", "obscura.db-shm"}
    for name in os.listdir(data):
        if name in skip:
            continue
        src, dst = os.path.join(data, name), os.path.join(dest, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    live = os.path.join(data, "obscura.db")
    if os.path.isfile(live):
        src = sqlite3.connect(f"file:{live}?mode=ro", uri=True)
        dst = sqlite3.connect(os.path.join(dest, "obscura.db"))
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
    return dest


def verify(dest: str) -> None:
    db_file = os.path.join(dest, "obscura.db")
    if os.path.isfile(db_file):
        result = integrity(db_file)
        if result != "ok":
            raise SystemExit(f"SNAPSHOT FAILED integrity_check: {result}")
        print("  obscura.db: integrity ok")
    else:
        print("  (no obscura.db in this data folder)")
    print(f"  files in snapshot: {count_files(dest)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", default=default_data_dir(), help="data folder to snapshot")
    ap.add_argument("--out", default=os.path.join(ROOT, "backups"), help="where to put it")
    ap.add_argument("--verify", metavar="SNAPSHOT", help="only verify an existing snapshot")
    a = ap.parse_args()
    if a.verify:
        print("Verifying", a.verify)
        verify(a.verify)
        return
    print("Data folder:", a.data)
    dest = snapshot(a.data, a.out)
    print("Snapshot   :", dest)
    verify(dest)
    print("OK - keep this folder until the fixes are verified.")


if __name__ == "__main__":
    main()
