# client.py
import argparse, socket, json, sys

def client_socket():
    serverName = "MyClientSocket"
    serverPort = 5001
    clientSocket = socket(AF_INET, SOCK_STREAM)
    clientSocket.connect((serverName, serverPort))
    while True:
        options = clientSocket.recv(1024).decode()
        chosen_option = int(input(options))
        clientSocket.send(chosen_option.encode())
        data = clientSocket.recv(1024).decode()

        # connection is over -> received data with 0 bytes
        if not data:
            break


    clientSocket.close()


def request(host: str, port: int, payload: dict) -> dict:
    """Send a single JSON-line request and return a single JSON-line response."""
    data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    with socket.create_connection((host, port), timeout=5) as s:
        s.sendall(data)
        buff = b""
        while True:
            chunk = s.recv(4096)
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
    ap.add_argument("--mode", choices=["calc", "gpt"], required=True)
    ap.add_argument("--expr", help="Expression for mode=calc")
    ap.add_argument("--prompt", help="Prompt for mode=gpt")
    ap.add_argument("--no-cache", action="store_true", help="Disable caching")
    args = ap.parse_args()

    if args.mode == "calc":
        if not args.expr:
            print("Missing --expr", file=sys.stderr); sys.exit(2)
        payload = {"mode": "calc", "data": {"expr": args.expr}, "options": {"cache": not args.no_cache}}
    else:
        if not args.prompt:
            print("Missing --prompt", file=sys.stderr); sys.exit(2)
        payload = {"mode": "gpt", "data": {"prompt": args.prompt}, "options": {"cache": not args.no_cache}}

    resp = request(args.host, args.port, payload)
    print(json.dumps(resp, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
