import sqlite3
from pathlib import Path
from flask import current_app, g


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
        g.db.create_function('CASEFOLD', 1, lambda value: str(value).casefold())
    return g.db


def close_db(error=None):
    connection = g.pop('db', None)
    if connection is not None:
        connection.close()


def migrate():
    db = get_db()
    db.execute('CREATE TABLE IF NOT EXISTS schema_migrations(name TEXT PRIMARY KEY)')
    for path in sorted((Path(current_app.root_path).parent / 'database/migrations').glob('*.sql')):
        if not db.execute('SELECT 1 FROM schema_migrations WHERE name=?', (path.name,)).fetchone():
            script = path.read_text(encoding='utf-8')
            escaped = path.name.replace("'", "''")
            db.executescript('BEGIN;\n' + script + f"\nINSERT INTO schema_migrations VALUES ('{escaped}');\nCOMMIT;")
