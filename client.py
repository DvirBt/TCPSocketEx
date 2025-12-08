# client.py
import argparse, socket, json, sys

# def client_socket():
#     serverName = "MyClientSocket"
#     serverPort = 5001
#     clientSocket = socket(AF_INET, SOCK_STREAM)
#     clientSocket.connect((serverName, serverPort))
#     while True:
#         options = clientSocket.recv(1024).decode()
#         chosen_option = int(input(options))
#         clientSocket.send(chosen_option.encode())
#         data = clientSocket.recv(1024).decode()
#
#         # connection is over -> received data with 0 bytes
#         if not data:
#             break
#
#
#     clientSocket.close()

def create_socket(host, port):
    # create a TCP socket and connection
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((host, port))
        print("Connected successfully! Type 'stop' to exit.")

    except ConnectionRefusedError:
        print("Could not connect to server.")

    except Exception as e:
        print(f"An error occurred: {e}")

    return client_socket


def get_args() -> dict:
    print ("Enter args \n")
    mode = input("Enter mode calc / gpt / stop \n")

    if mode == "stop":
        return {"mode": "stop"}

    no_cache = input("Enter y to disable cache, otherwise - not disabled \n")
    # if cache == "y":

    if mode == "calc":
        expression = input("Enter expression \n")
        payload = {"mode": "calc", "data": {"expr": expression}, "options": {"cache": not no_cache}}

    elif mode == "gpt":
        prompt = input("Enter prompt to chatGPT \n")
        payload = {"mode": "gpt", "data": {"prompt": prompt}, "options": {"cache": not no_cache}}

    else:
        payload = {"mode": "unknown"}

    return payload

    # ap.add_argument("--mode", choices=["calc", "gpt"], required=True)
    # ap.add_argument("--expr", help="Expression for mode=calc")
    # ap.add_argument("--prompt", help="Prompt for mode=gpt")
    # ap.add_argument("--no-cache", action="store_true", help="Disable caching")

    # elif args.mode == "calc":
    #     if not args.expr:
    #         print("Missing --expr", file=sys.stderr);
    #         sys.exit(2)
    #     payload = {"mode": "calc", "data": {"expr": args.expr}, "options": {"cache": not args.no_cache}}
    # else:
    #     if not args.prompt:
    #         print("Missing --prompt", file=sys.stderr);
    #         sys.exit(2)
    #     payload = {"mode": "gpt", "data": {"prompt": args.prompt}, "options": {"cache": not args.no_cache}}

    # resp = request(client_socket, payload)
    # print(json.dumps(resp, ensure_ascii=False, indent=2))




def request(client_socket, payload: dict) -> dict:
    """Send a single JSON-line request and return a single JSON-line response."""
    data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")

    #with socket.create_connection((host, port), timeout=5) as s:
    client_socket.sendall(data)
    buff = b""
    while True:
        chunk = client_socket.recv(4096)
        if not chunk:
            break
        buff += chunk
        if b"\n" in buff:
            line, _, _ = buff.partition(b"\n")
            return json.loads(line.decode("utf-8"))
    return {"ok": False, "error": "No response"}

def main():

    ap = argparse.ArgumentParser(description="Client (calc/gpt over JSON TCP)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5555)
    args = ap.parse_args()

    client_socket = create_socket(args.host, args.port)

    # loop until client requests to stop
    while True:
        payload = get_args()
        if payload["mode"] == "stop":
            print ("Client entered stop")
            break

        elif payload["mode"] == "unknown":
            print ("Client entered unknown mode")
            pass
        else:
            print ("request is processing in the server")
            request(client_socket, payload)

    client_socket.close()


if __name__ == "__main__":
    main()
