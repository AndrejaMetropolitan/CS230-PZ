import json
from datetime import datetime, timezone
from pathlib import Path
import socket
import threading
from urllib import response
from Blockchain import Blockchain
from Baza import (
    initialize_database,
    get_candidates,
    create_user,
    authenticate_user,
    issue_voting_token,
    candidate_exists,
    get_unused_token_hash,
    mark_token_as_used
)

HOST = "127.0.0.1"
PORT = 5000
MAX_MESSAGE_SIZE = 4096
LOG_FILE = Path(__file__).resolve().parent / "data" / "server.log"
log_lock = threading.Lock()
blockchain = Blockchain()
vote_lock = threading.Lock()


def send_json(client_socket, message):
    data = json.dumps(message).encode("utf-8") + b"\n"
    client_socket.sendall(data)


def receive_json(client_socket):
    buffer = b""

    while b"\n" not in buffer:
        
        chunk = client_socket.recv(MAX_MESSAGE_SIZE)
        if not chunk:
            break
        buffer += chunk

        if len(buffer) > MAX_MESSAGE_SIZE:
            raise ValueError("Poruka je prevelika.")
    
    raw_message = buffer.split(b"\n", 1)[0].decode("utf-8")
    return json.loads(raw_message)

def write_log(record):
    LOG_FILE.parent.mkdir(exist_ok=True)

    with log_lock:
        with open(LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(record) + "\n")

def log_request(handler):
    """
    Custom interceptor/wrapper:
    evidentira obradu zahteva bez cuvanja lozinke ili tokena
    """

    def wrapper (request, address):
        action = request.get("action") if isinstance(request, dict) else "invalid"

        try:
            response = handler(request, address)

            write_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "client_ip": address[0],
                "action": action,
                "success": response.get("success", False)
            })

            return response

        except Exception as error:
            write_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "client_ip": address[0],
                "action": action,
                "success": False,
                "error": str(error)
            })
            raise

    return wrapper

@log_request
def process_request(request, address):

    if not isinstance(request, dict):
        return {
            "success": False,
            "message": "Poruka mora biti u JSON formatu."
        }
    
    action = request.get("action")

    if action == "ping":
        return {
            "success": True,
            "message": "pong"
        }

    if action == "server_info":
        return {
            "success": True,
            "message": f"Server je pokrenut na {HOST}:{PORT}"
        }

    if action == "get_candidates":
        return {
            "success": True,
            "candidates": get_candidates()
        }

    if action == "register":
        username = request.get("username")
        password = request.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            return {
                "success": False,
                "message": "Korisnicko ime i lozinka su obavezni i moraju biti tekst"
            }
        success, message = create_user(username, password)

        return {
            "success": success,
            "message": message
        }

    if action == "login":
        username = request.get("username")
        password = request.get("password")

        if not isinstance(username, str) or not isinstance(password, str):
            return {
                "success": False,
                "message": "Korisnicko ime i lozinka su obavezni i moraju biti tekst"
            }
        success, message = authenticate_user(username, password)
        return {
            "success": success,
            "message": message
        }

    if action == "issue_token":
        username = request.get("username", "")
        password = request.get("password", "")

        if not isinstance(username, str) or not isinstance(password, str):
            return {
                "success": False,
                "message": "Korisnicko ime i lozinka su obavezni i moraju biti tekst"
            }

        success, message, token = issue_voting_token(username, password)

        response = {
            "success": success,
            "message": message
        }

        if success:
            response["token"] = token

        return response

    if action == "get_blockchain":
        return {
            "success": True,
            "chain": blockchain.get_chain()
        }

    if action == "validate_blockchain":
        success, message = blockchain.validate_chain()

        return {
            "success": success,
            "message": message
        }

    if action == "vote":
        token = request.get("token", "")
        candidate_id = request.get("candidate_id")

        if not isinstance(token, str) or not token:
            return {
                "success": False,
                "message": "Token je obavezan."
            }

        if type(candidate_id) is not int:
            return {
                "success": False,
                "message": "ID kandidata je obavezan i mora biti ceo broj."
            }

        with vote_lock:
            if not candidate_exists(candidate_id):
                return {
                    "success": False,
                    "message": "Kandidat ne postoji."
                }

            token_hash = get_unused_token_hash(token)

            if token_hash is None:
                return {
                    "success": False,
                    "message": "Token je neispravan ili je vec iskoriscen."
                }

            success, message = blockchain.add_vote_block(
                candidate_id, 
                token_hash
            )
            if not success:
                return {
                    "success": False,
                    "message": message
                }
            if not mark_token_as_used(token_hash):
                return {
                    "success": False,
                    "message": "Token nije mogao biti oznacen kao iskoriscen."
                }
        
        return {
            "success": True,
            "message": "Glas je uspesno zabelezen."
        }
                
    if action == "get_results":
        is_valid, message = blockchain.validate_chain()

        if not is_valid:
            return {
                "success": False,
                "message": f"Blockchain nije validan: {message}"
            }

        vote_counts = blockchain.get_vote_counts()
        results = []

        for candidate in get_candidates():
            candidate_id = candidate["id"]

            results.append({
                "candidate_id": candidate_id,
                "candidate_name": candidate["name"],
                "votes": vote_counts.get(candidate_id, 0)
            })

        return {
            "success": True,
            "results": results
        }

    return {
        "success": False,
        "message": "Nepoznata akcija."
    }

def handle_client(client_socket, address):
    print(f"Klijent povezan: {address}")

    try:
        request = receive_json(client_socket)
        print(f"Zahtev od {address}: {request}")

        response = process_request(request, address)
        send_json(client_socket, response)

    except json.JSONDecodeError:
        send_json(client_socket, {
            "success": False,
            "message": "Neispravan JSON format."
        })

    except ValueError as error:
        send_json(client_socket, {
            "success": False,
            "message": str(error)
        })

    except Exception as error:
        print(f"Greska sa klijentom {address}: {error}")

    finally:
        client_socket.close()
        print(f"Klijent odjavljen: {address}")


def start_server():
    initialize_database()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen()

    print(f"Server je pokrenut na {HOST}:{PORT}")

    while True:
        client_socket, address = server_socket.accept()

        client_thread = threading.Thread(
            target=handle_client,
            args=(client_socket, address),
            daemon=True
        )
        client_thread.start()


if __name__ == "__main__":
    start_server()