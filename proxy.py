# proxy.py
import argparse, socket, threading, json

from server import LRUCache


def get_from_cache(client_request, cache_data):
    try:
        data = json.loads(client_request.decode("utf-8"))
        if data["mode"] == "calc":
            # true means we got a hit in the cache
            if data["expr"] in cache_data and cache_data[data["expr"]] is not None:
                return cache_data[data["expr"]], True
            else:
                cache_data[data["expr"]] = None
                return data["expr"], False

        elif data["mode"] == "gpt":
            if data["prompt"] in cache_data and cache_data[data["prompt"]] is not None:
                return cache_data[data["prompt"]], True # maybe save the whole json?
            else:
                cache_data[data["prompt"]] = None
                return data["prompt"], False

        # an invalid json mode input (consider stop and unknown)
        else:
            return None

    except json.JSONDecodeError:
        raise Exception("Invalid JSON")


def save_to_cache(request, answer, cache_data):
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

"""
def handle(c, sh, sp, cache_data):

    save = False # flag for save to the cache
    request_key = None
    first_data = recv_until_newline(c)
    if not first_data:
        return
    try:
        hit = get_from_cache(first_data, cache_data)
        if hit[0] is not None and hit[1] is True:
            c.send(hit[0].encode("utf-8"))
            print ("Received from the proxy's cache")
            return
        else:
            print ("Not found in the cache")
            save = True # save the response from the server
            request_key = hit[0]

    except Exception:
        pass

    with c:
        try:
            with socket.create_connection((sh, sp)) as s:
                s.sendall(first_data)

                t1 = threading.Thread(target=pipe, args=(c, s), daemon=True)
                t2 = threading.Thread(target=pipe, args=(s, c, request_key, save, cache_data), daemon=True)
                # try to get data from the cache

                t1.start(); t2.start()
                t1.join(); t2.join()
                # add the result to the cache

        except Exception as e:
            try: c.sendall((json.dumps({"ok": False, "error": f"Proxy error: {e}"})+"\n").encode("utf-8"))
            except Exception: pass
"""

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

                server_socket.sendall(first_data) # send the request for the operation
                response = recv_until_newline(server_socket) # got the output
                if response is None:
                    break

                c.sendall(response) # return the response to the client
                if request_key is not None:
                    print ("Saving to the proxy's cache")
                    save_to_cache(request_key, response, cache_data)

            except Exception as e:
                try: c.sendall((json.dumps({"ok": False, "error": f"Proxy error: {e}"})+"\n").encode("utf-8"))
                except Exception: pass

    finally:
        try:
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
