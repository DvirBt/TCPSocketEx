# proxy.py
import argparse, socket, threading, json

from server import LRUCache


def get_from_cache(client_request, cache_data):
    print ("Trying to get from cache")
    try:
        data = json.loads(client_request.decode("utf-8"))
        mode = data.get("mode")

        if mode == "calc":
            # true means we got a hit in the cache
            expr = data.get("expr")
            if expr in cache_data and cache_data[expr] is not None:
                print ("Found in cache")
                return cache_data[expr], True
            else:
                print ("Not found in cache")
                cache_data[expr] = None
                return expr, False

        elif mode == "gpt":
            prompt = data.get("prompt")
            if prompt in cache_data and cache_data[prompt] is not None:
                print ("Found in cache")
                return cache_data[prompt], True # maybe save the whole json?
            else:
                print ("Not found in cache")
                cache_data[prompt] = None
                return prompt, False

        # an invalid json mode input (consider stop and unknown)
        else:
            return None

    except KeyError:
        print ("Error")
        raise Exception("Error")

    except json.JSONDecodeError:
        raise Exception("Invalid json decode")


def save_to_cache(request, answer, cache_data):
    print ("Saved to cache")
    cache_data[request] = answer


def pipe(src, dst, key = None, save = False, cache_data = None):
    """Bi-directional byte piping helper."""
    buffer = b"" # if many packets are retrieved -> save them in a buffer and save the buffer at the cache
    try:
        while True:
            data = src.recv(4096)
            if not data:
                break

            dst.sendall(data)
            if save:
                buffer += data

    except Exception:
        print ("Pipe exception")
        pass
    finally:
        try:
            if save and key is not None and cache_data is not None:
                save_to_cache(key, buffer.decode("utf-8"), cache_data)
            dst.shutdown(socket.SHUT_WR)
        except Exception: pass

def main():
    ap = argparse.ArgumentParser(description="Transparent TCP proxy (optional)")
    ap.add_argument("--listen-host", default="127.0.0.1")
    ap.add_argument("--listen-port", type=int, default=5554)
    ap.add_argument("--server-host", default="127.0.0.1")
    ap.add_argument("--server-port", type=int, default=5555)
    args = ap.parse_args()

    cache_data = LRUCache(512)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((args.listen_host, args.listen_port))
        s.listen(16)
        print(f"[proxy] {args.listen_host}:{args.listen_port} -> {args.server_host}:{args.server_port}")
        while True:
            c, addr = s.accept()
            threading.Thread(target=handle, args=(c, args.server_host, args.server_port, cache_data), daemon=True).start()


def recv_until_newline(sock):
    buffer = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            return None

        buffer += chunk

        # check if delimiter is found
        if b"\n" in buffer:
            return buffer


def handle(c, sh, sp, cache_data):

    try:
        server_socket = None
        while True:
            request_key = None
            first_data = recv_until_newline(c)
            if not first_data:
                return
            try:
                hit = get_from_cache(first_data, cache_data)
                if hit[0] is not None and hit[1] is True:
                    print ("Found in cache, returning to client")
                    c.send(hit[0].encode("utf-8"))
                    print ("Received from the proxy's cache")
                    continue

                else:
                    print ("Not found in the cache")
                    request_key = hit[0]

            except Exception:
                pass


            try:
                if server_socket is None:
                    server_socket = socket.create_connection((sh, sp))

                print ("Send the data to the server")
                server_socket.sendall(first_data) # send the request for the operation
                response = recv_until_newline(server_socket) # got the output
                print ("Got response from the server")
                if response is None:
                    print ("Response is None")
                    break

                print ("Response is not None")
                c.sendall(response) # return the response to the client
                if request_key is not None:
                    print ("Request key is not none, saving to the proxy's cache")
                    save_to_cache(request_key, response, cache_data)

            except Exception as e:
                try: c.sendall((json.dumps({"ok": False, "error": f"Proxy error: {e}"})+"\n").encode("utf-8"))
                except Exception: pass

    finally:
        try:
            print ("Shutting down")
            c.shutdown(socket.SHUT_RDWR)
            c.close()
        except Exception:
            c.close()

        if server_socket:
            try:
                server_socket.close()
            except Exception:
                pass

if __name__ == "__main__":
    main()
