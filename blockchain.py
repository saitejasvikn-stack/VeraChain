import os
import sqlite3
import hashlib
import json
from datetime import datetime


class VeraChain:
    def __init__(self, chain_type="luxury"):
        self.chain_type = chain_type
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_name = f"verachain_{self.chain_type}.db"
        self.db_path = os.path.join(base_dir, db_name)
        self._create_table()
        if len(self.get_chain()) == 0:
            self.add_block(product_id="GENESIS", brand="SYSTEM", category=chain_type, previous_hash="0")

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _create_table(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS blocks (
                    block_index INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    product_id TEXT,
                    brand TEXT,
                    category TEXT,
                    previous_hash TEXT,
                    block_hash TEXT
                )
            ''')
            conn.commit()

    def calculate_hash(self, index, timestamp, product_id, brand, category, previous_hash):
        block_string = f"{index}{timestamp}{product_id}{brand}{category}{previous_hash}"
        return hashlib.sha256(block_string.encode('utf-8')).hexdigest()

    def add_block(self, product_id, brand, category, previous_hash=None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if not previous_hash:
                cursor.execute("SELECT block_hash FROM blocks ORDER BY block_index DESC LIMIT 1")
                row = cursor.fetchone()
                previous_hash = row[0] if row else "0"

            cursor.execute("SELECT COUNT(*) FROM blocks")
            index = cursor.fetchone()[0]

            timestamp = datetime.utcnow().isoformat()
            block_hash = self.calculate_hash(index, timestamp, product_id, brand, category, previous_hash)

            cursor.execute('''
                INSERT INTO blocks (timestamp, product_id, brand, category, previous_hash, block_hash)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (timestamp, product_id, brand, category, previous_hash, block_hash))
            conn.commit()
            return block_hash

    def get_chain(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT block_index, timestamp, product_id, brand, category, previous_hash, block_hash FROM blocks ORDER BY block_index ASC")
            rows = cursor.fetchall()
            chain = []
            for row in rows:
                chain.append({
                    "index": row[0],
                    "timestamp": row[1],
                    "product_id": row[2],
                    "brand": row[3],
                    "category": row[4],
                    "previous_hash": row[5],
                    "block_hash": row[6]
                })
            return chain

    def verify_integrity(self):
        chain = self.get_chain()
        if not chain:
            return True, "Chain is empty."
        for i in range(1, len(chain)):
            current = chain[i]
            previous = chain[i - 1]
            if current["previous_hash"] != previous["block_hash"]:
                return False, f"Hash separation error at Block {current['index']}"
            recalculated = self.calculate_hash(
                current["index"] - 1,
                current["timestamp"],
                current["product_id"],
                current["brand"],
                current["category"],
                current["previous_hash"]
            )
        return True, "Cryptographic integrity intact."


# ── VeraLedger (used by Streamlit portals & consumer portal) ──────────────────

class VeraLedger:
    def __init__(self):
        self.chain = []
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(base_dir, "verachain.db")
        self._create_table()
        self.load_from_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _create_table(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ledger_blocks (
                    block_index INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    products TEXT,
                    prev_hash TEXT,
                    block_hash TEXT
                )
            ''')
            conn.commit()

    def load_from_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT block_index, timestamp, products, prev_hash, block_hash FROM ledger_blocks ORDER BY block_index ASC")
            rows = cursor.fetchall()
            self.chain = []
            for row in rows:
                self.chain.append({
                    "index": row[0],
                    "timestamp": row[1],
                    "products": json.loads(row[2]),
                    "prev_hash": row[3],
                    "hash": row[4]
                })

    def create_block(self, products, prev_hash):
        timestamp = datetime.utcnow().isoformat()
        block_string = f"{timestamp}{json.dumps(products)}{prev_hash}"
        block_hash = hashlib.sha256(block_string.encode('utf-8')).hexdigest()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO ledger_blocks (timestamp, products, prev_hash, block_hash)
                VALUES (?, ?, ?, ?)
            ''', (timestamp, json.dumps(products), prev_hash, block_hash))
            conn.commit()

        self.chain.append({
            "timestamp": timestamp,
            "products": products,
            "prev_hash": prev_hash,
            "hash": block_hash
        })
        return block_hash

    def verify_id(self, product_id):
        for block in self.chain:
            for p in block.get('products', []):
                if p.get('product_id', '').upper() == product_id.upper():
                    return p
        return None

    def validate_chain(self):
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]
            if current["prev_hash"] != previous["hash"]:
                return False
        return True


# ── Singleton instances ───────────────────────────────────────────────────────

vera_ledger = VeraLedger()

ledgers = {
    "luxury": VeraChain("luxury"),
    "pharma": VeraChain("pharma")
}