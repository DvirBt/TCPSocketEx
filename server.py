# server.py
'''
Enabling real GPT calls (optional):
1. Install deps: pip install -r requirements.txt.
2. Create a .env file with OPENAI_API_KEY=... .
3. Replace call_gpt() in server.py with the real implementation shown in the comments, or keep the stub.
'''
import argparse, socket, json, time, threading, math, os, ast, operator, collections
from typing import Any, Dict
from openai import OpenAI

# ---------------- LRU Cache (simple) ----------------
class LRUCache:
    """Minimal LRU cache based on OrderedDict."""
    def __init__(self, capacity: int = 128):
        self.capacity = capacity
        self._d = collections.OrderedDict()

    def get(self, key):
        if key not in self._d:
            return None
        self._d.move_to_end(key)
        return self._d[key]

    def set(self, key, value):
        self._d[key] = value
        self._d.move_to_end(key)
        if len(self._d) > self.capacity:
            self._d.popitem(last=False)

# ---------------- Safe Math Eval (no eval) ----------------
_ALLOWED_FUNCS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan, "sqrt": math.sqrt,
    "log": math.log, "exp": math.exp, "max": max, "min": min, "abs": abs,
}
_ALLOWED_CONSTS = {"pi": math.pi, "e": math.e}
_ALLOWED_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg,
    ast.UAdd: operator.pos, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
}

def _eval_node(node):
    """Evaluate a restricted AST node safely."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("illegal constant type")
    if hasattr(ast, "Num") and isinstance(node, ast.Num):  # legacy fallback
        return node.n
    if isinstance(node, ast.Name):
        if node.id in _ALLOWED_CONSTS:
            return _ALLOWED_CONSTS[node.id]
        raise ValueError(f"unknown symbol {node.id}")
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
            raise ValueError("illegal function call")
        args = [_eval_node(a) for a in node.args]
        return _ALLOWED_FUNCS[node.func.id](*args)
    raise ValueError("illegal expression")

def safe_eval_expr(expr: str) -> float:
    """Parse and evaluate the expression safely using ast (no eval)."""
    tree = ast.parse(expr, mode="eval")

    # check validation
    try:
        result = float(_eval_node(tree.body))
    except ValueError:
        result = None

    return result


# ---------------- GPT Call (stub by default) ----------------
def call_gpt(prompt: str) -> str:
    """
    Stub for GPT call — returns a placeholder string.
    Replace this with a real OpenAI call if desired.
    """
    # return f"[GPT-STUB] Received a prompt of length {len(prompt)} chars."
    client = OpenAI(api_key="YOUR_API_KEY")

    response = client.chat.completions.create(
        model="gpt-5",  # or gpt-5, gpt-4.1, etc.
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message["content"]

# ---------------- Server core ----------------
def handle_request(msg: Dict[str, Any], cache: LRUCache) -> Dict[str, Any]:
    print ("Received request")
    mode = msg.get("mode")
    data = msg.get("data") or {}
    options = msg.get("options") or {}
    use_cache = bool(options.get("cache", True))

    started = time.time()
    cache_key = json.dumps(msg, sort_keys=True)

    if use_cache:
        hit = cache.get(cache_key)
        if hit is not None:
            return {"ok": True, "result": hit, "meta": {"from_cache": True, "took_ms": int((time.time()-started)*1000)}}

    try:
        if mode == "calc":
            print ("Client chose calc")
            expr = data.get("expr")
            if not expr or not isinstance(expr, str):
                print ("Bad expression")
                return {"ok": False, "error": "Bad request: 'expr' is required (string)"}
            res = safe_eval_expr(expr)
            if res is None:
                print ("result is None")
                return {"ok": False, "error": "Bad request: 'expr' is not a valid expression"}
            print (f"the result is: {res}")
            return {"ok": True, "result": res, "meta": {"from_cache": False, "took_ms": int((time.time()-started)*1000)}}

        elif mode == "gpt":
            print ("Client chose gpt")
            prompt = data.get("prompt")
            if not prompt or not isinstance(prompt, str):
                print ("bad prompt")
                return {"ok": False, "error": "Bad request: 'prompt' is required (string)"}
            res = call_gpt(prompt)
            print (f"gpt result: {res}")
        else:
            return {"ok": False, "error": "Bad request: unknown mode"}

        took = int((time.time()-started)*1000)
        if use_cache:
            cache.set(cache_key, res)
        return {"ok": True, "result": res, "meta": {"from_cache": False, "took_ms": took}}
    except Exception as e:
        return {"ok": False, "error": f"Server error: {e}"}

def serve(host: str, port: int, cache_size: int):
    cache = LRUCache(cache_size)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(16)
        print(f"[server] listening on {host}:{port} (cache={cache_size})")
        while True:
            conn, addr = s.accept()
            print ("Accepted connection")
            threading.Thread(target=handle_client, args=(conn, addr, cache), daemon=True).start()

def handle_client(conn: socket.socket, addr, cache: LRUCache):
    with conn:
        try:
            raw = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                raw += chunk
                while b"\n" in raw:
                    line, _, rest = raw.partition(b"\n")
                    raw = rest
                    msg = json.loads(line.decode("utf-8"))
                    resp = handle_request(msg, cache)
                    out = (json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8")
                    conn.sendall(out)
        except Exception as e:
            try:
                conn.sendall((json.dumps({"ok": False, "error": f"Malformed: {e}"} ) + "\n").encode("utf-8"))
            except Exception:
                pass

def main():
    ap = argparse.ArgumentParser(description="JSON TCP server (calc/gpt) — student skeleton")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5555)
    ap.add_argument("--cache-size", type=int, default=128)
    args = ap.parse_args()
    serve(args.host, args.port, args.cache_size)

if __name__ == "__main__":
    main()
