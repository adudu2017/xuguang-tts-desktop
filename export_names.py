"""Persistent daily sequence shared by all suggested export names."""
from datetime import date
from contextlib import closing
from pathlib import Path
import sqlite3


def next_name(base, prefix, suffix='', day=None):
    day = day or date.today().strftime('%Y%m%d')
    data = Path(base) / 'data'
    data.mkdir(parents=True, exist_ok=True)
    # Reserve before opening the dialog so concurrent windows cannot suggest the
    # same batch. Cancelled dialogs may leave gaps; numbers are never recycled.
    with closing(sqlite3.connect(data / 'export_sequences.sqlite3', timeout=10)) as db:
        db.execute('CREATE TABLE IF NOT EXISTS sequences (day TEXT PRIMARY KEY, value INTEGER NOT NULL)')
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT value FROM sequences WHERE day=?', (day,)).fetchone()
        batch = row[0] + 1 if row else 1
        db.execute('INSERT OR REPLACE INTO sequences VALUES (?,?)', (day, batch))
        db.commit()
    return f'{prefix}{day}{batch:03d}{suffix}'
