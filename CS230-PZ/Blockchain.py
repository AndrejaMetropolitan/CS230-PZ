import hashlib
from itertools import chain
import json
from datetime import datetime, timezone
from pathlib import Path
import re
from tkinter import SE

class Blockchain:
    def __init__(self):
        project_directory = Path(__file__).resolve().parent
        data_directory = project_directory / "data"
        data_directory.mkdir(exist_ok=True)

        self.file_path = data_directory / "blockchain.json"

        if not self.file_path.exists():
            genesis_block = self.create_genesis_block()
            self.save_chain([genesis_block])

    def calculate_hash(
        self,
        index,
        timestamp,
        candidate_id,
        token_hash,
        previous_hash,
    ):
        block_data ={
            "index": index,
            "timestamp": timestamp,
            "candidate_id": candidate_id,
            "token_hash": token_hash,
            "previous_hash": previous_hash,
        }

        encoded_data = json.dumps(
            block_data,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

        return hashlib.sha256(encoded_data).hexdigest()

    def create_genesis_block(self):
        timestamp = datetime.now(timezone.utc).isoformat()

        block = {
            "index": 0,
            "timestamp": timestamp,
            "candidate_id": None,
            "token_hash": None,
            "previous_hash": "0",
        }

        block["hash"] = self.calculate_hash(
            block["index"],
            block["timestamp"],
            block["candidate_id"],
            block["token_hash"],
            block["previous_hash"]
        )

        return block

    def load_chain(self):
        with open(self.file_path, "r", encoding="utf-8" ) as file:
            return json.load(file)

    def save_chain(self, chain):
        temporary_path = self.file_path.with_suffix(".tmp")

        with open(temporary_path, "w", encoding="utf-8") as file:
            json.dump(chain, file, indent=4)

        temporary_path.replace(self.file_path)

    def get_chain(self):
        return self.load_chain()

    def validate_chain(self):
        chain = self.load_chain()

        if not chain:
            return False, "Blockchain je prazan."

        for index, block in enumerate(chain):
            expected_hash = self.calculate_hash(
                block["index"],
                block["timestamp"],
                block["candidate_id"],
                block["token_hash"],
                block["previous_hash"]
            )

            if block["hash"] != expected_hash:
                return False, f"Neispravan hash u bloku {index}."

            if index == 0:
                if block["previous_hash"] != "0":
                    return False, "Neispravan prethodni hash u genesis bloku."
            elif block["previous_hash"] != chain[index - 1]["hash"]:
                return False, f"Neispravan prethodni hash u bloku {index}."

        return True, "Blockchain je validan."

    def add_vote_block(self, candidate_id, token_hash):
        is_valid, message = self.validate_chain()

        if not is_valid:
            return False, message

        chain = self.load_chain()
        previous_block = chain[-1]

        block = {
            "index": len(chain),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "candidate_id": candidate_id,
            "token_hash": token_hash,
            "previous_hash": previous_block["hash"],
        }

        block["hash"] = self.calculate_hash(
            block["index"],
            block["timestamp"],
            block["candidate_id"],
            block["token_hash"],
            block["previous_hash"]
        )

        chain.append(block)
        self.save_chain(chain)

        return True, "Glas je uspesno dodat u blockchain."

    def get_vote_counts(self):
        counts = {}

        for block in self.load_chain()[1:]:
            candidate_id = block.get("candidate_id")

            if isinstance(candidate_id, int):
                counts[candidate_id] = counts.get(candidate_id, 0) + 1
        return counts