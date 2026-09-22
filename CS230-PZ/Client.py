import json
import socket

HOST = "127.0.0.1"
PORT = 5000
MAX_MESSAGE_SIZE = 4096

current_token = None


def send_request(request):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        client_socket.connect((HOST, PORT))

        data = json.dumps(request).encode("utf-8") + b"\n"
        client_socket.sendall(data)

        buffer = b""

        while b"\n" not in buffer:
            chunk = client_socket.recv(MAX_MESSAGE_SIZE)

            if not chunk:
                raise ConnectionError("Server je prekinuo vezu.")

            buffer += chunk

        response = buffer.split(b"\n", 1)[0].decode("utf-8")
        return json.loads(response)


def print_candidates():
    response = send_request({"action": "get_candidates"})

    if not response["success"]:
        print(response["message"])
        return

    print("\nDostupni kandidati:")

    for candidate in response["candidates"]:
        print(f'{candidate["id"]}. {candidate["name"]}')


def register():
    username = input("Korisnicko ime: ")
    password = input("Lozinka: ")

    response = send_request({
        "action": "register",
        "username": username,
        "password": password
    })

    print(response["message"])


def login():
    username = input("Korisnicko ime: ")
    password = input("Lozinka: ")

    response = send_request({
        "action": "login",
        "username": username,
        "password": password
    })

    print(response["message"])


def issue_token():
    global current_token

    username = input("Korisnicko ime: ")
    password = input("Lozinka: ")

    response = send_request({
        "action": "issue_token",
        "username": username,
        "password": password
    })

    print(response["message"])

    if response["success"]:
        current_token = response["token"]
        print("Token je sacuvan samo u trenutnoj klijent sesiji.")


def vote():
    global current_token

    if current_token is None:
        current_token = input("Unesi glasacki token: ").strip()

    print_candidates()

    try:
        candidate_id = int(input("Izaberi ID kandidata: "))
    except ValueError:
        print("ID kandidata mora biti ceo broj.")
        return

    response = send_request({
        "action": "vote",
        "token": current_token,
        "candidate_id": candidate_id
    })

    print(response["message"])

    if response["success"]:
        current_token = None


def show_results():
    response = send_request({"action": "get_results"})

    if not response["success"]:
        print(response["message"])
        return

    print("\nRezultati:")

    for result in response["results"]:
        print(f'{result["candidate_name"]}: {result["votes"]} glas(ova)')


def validate_blockchain():
    response = send_request({"action": "validate_blockchain"})
    print(response["message"])


def show_menu():
    print("""
=== BLOCKCHAIN GLASANJE ===
1. Registracija
2. Prijava
3. Preuzmi glasacki token
4. Prikazi kandidate
5. Glasaj
6. Prikazi rezultate
7. Proveri blockchain
0. Izlaz
""")


def main():
    while True:
        show_menu()
        choice = input("Izaberi opciju: ").strip()

        try:
            if choice == "1":
                register()
            elif choice == "2":
                login()
            elif choice == "3":
                issue_token()
            elif choice == "4":
                print_candidates()
            elif choice == "5":
                vote()
            elif choice == "6":
                show_results()
            elif choice == "7":
                validate_blockchain()
            elif choice == "0":
                print("Dovidjenja.")
                break
            else:
                print("Nepostojeca opcija.")

        except (ConnectionError, OSError):
            print("Nije moguce povezivanje sa serverom.")
        except json.JSONDecodeError:
            print("Server je poslao neispravan odgovor.")


if __name__ == "__main__":
    main()