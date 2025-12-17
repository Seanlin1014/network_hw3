# protocol.py
import json

def encode_message(msg_type, **kwargs):
    data = {"type": msg_type}
    data.update(kwargs)
    return json.dumps(data).encode("utf-8")

def decode_message(raw_bytes):
    if not raw_bytes:
        return None
    try:
        return json.loads(raw_bytes.decode("utf-8"))
    except Exception:
        return None