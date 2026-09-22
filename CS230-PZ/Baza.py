import sqlite3
from pathlib import Path
import hashlib
import secrets
from datetime import datetime, timezone

PROJECT_DIRECTORY = Path(__file__).resolve().parent
DATA_DIRECTORY = PROJECT_DIRECTORY / "data"
DATABASE_PATH = DATA_DIRECTORY / "glasanje.db"

def get_database_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection

def initialize_database():
    DATA_DIRECTORY.mkdir(exist_ok=True)

    with get_database_connection() as connection:

        connection.execute(
            """
                CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                has_received_token INTEGER NOT NULL DEFAULT 0)
            """
            )

        connection.execute(
            """
                CREATE TABLE IF NOT EXISTS voting_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash TEXT NOT NULL UNIQUE,
                issued_at TEXT NOT NULL,
                used INTEGER NOT NULL DEFAULT 0)
            """
            )

        connection.execute(
            """
                CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE)
            """
            )

        connection.execute(
            "INSERT OR IGNORE INTO candidates (id, name) VALUES (?, ?)",
            (1, "Kandidat A")
        )
        connection.execute(
            "INSERT OR IGNORE INTO candidates (id, name) VALUES (?, ?)",
            (2, "Kandidat B")
        )
        connection.execute(
            "INSERT OR IGNORE INTO candidates (id, name) VALUES (?, ?)",
            (3, "Kandidat C")
        )

def get_candidates():
    with get_database_connection() as connection:
        rows = connection.execute(
            "SELECT id, name FROM candidates"
        ).fetchall()
    return [dict(row) for row in rows]

def hash_password(password):
    salt = secrets.token_hex(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256", 
        password.encode("utf-8"), 
        salt.encode("utf-8"), 
        100000
    ).hex()

    return f"{salt}${password_hash}"

def verify_password(password, stored_password):
    salt, stored_hash = stored_password.split("$", 1)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256", 
        password.encode("utf-8"), 
        salt.encode("utf-8"), 
        100000
    ).hex()

    return secrets.compare_digest(password_hash, stored_hash)

def create_user(username, password):
    username = username.strip()
    
    if len(username) < 3 or len(username) > 20:
        return False, "Korisnicko ime mora biti izmedu 3 i 20 znakova."

    if len(password) < 6:
        return False, "Lozinka mora imati barem 6 znakova."

    password_hash = hash_password(password)

    try:
        with get_database_connection() as connection:
            connection.execute(
                """
                INSERT INTO users (username, password_hash) 
                VALUES (?, ?)
                """,
                (username, password_hash)
            )
        return True, "Korisnik je uspesno kreiran."
    except sqlite3.IntegrityError:
        return False, "Korisnicko ime vec postoji."

def authenticate_user(username, password):
    with get_database_connection() as connection:
        user = connection.execute(
            """
            SELECT * 
            FROM users 
            WHERE username = ?
            """,
            (username.strip(),)
        ).fetchone()

    if user is None:
        return False, "Korisnicko ime ne postoji."

    if not verify_password(password, user["password_hash"]):
        return False, "Pogresna lozinka ili korisnicko ime"
    
    return True, "Uspesna autentifikacija."

def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def issue_voting_token(username, password):
    with get_database_connection() as connection:
        user = connection.execute(
            """
            SELECT * 
            FROM users 
            WHERE username = ?
            """,
            (username.strip(),)
        ).fetchone()

        if user is None or not verify_password(password, user["password_hash"]):
            return False, "Korisnicko ime ili lozinka je netacna.", None

        if user["has_received_token"] == 1:
            return False, "Korisnik je vec dobio token za glasanje.", None

        token = secrets.token_urlsafe(32)
        token_hash = hash_token(token)
        issued_at = datetime.now(timezone.utc).isoformat()

        connection.execute(
            """
            INSERT INTO voting_tokens (token_hash, issued_at, used) 
            VALUES (?, ?, 0)
            """,
            (token_hash, issued_at)
        )

        connection.execute(
            """
            UPDATE users 
            SET has_received_token = 1 
            WHERE id = ?
            """,
            (user["id"],)
        )
    return True, "Glasacki token je upsesno izdat", token

def candidate_exists(candidate_id):
    with get_database_connection() as connection:
        candidate = connection.execute(
            """
            SELECT id 
            FROM candidates 
            WHERE id = ?
            """,
            (candidate_id,)
        ).fetchone()
    return candidate is not None

def get_unused_token_hash(token):
    token_hash = hash_token(token)

    with get_database_connection() as connection:
        token_row = connection.execute(
            """
            SELECT id 
            FROM voting_tokens 
            WHERE token_hash = ? AND used = 0
            """,
            (token_hash,)
        ).fetchone()
    if token_row is None:
        return None

    return token_hash

def mark_token_as_used(token_hash):
    with get_database_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE voting_tokens 
            SET used = 1 
            WHERE token_hash = ?
            """,
            (token_hash,)
        )

    return cursor.rowcount == 1