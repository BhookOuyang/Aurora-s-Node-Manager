# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BhookOuyang <https://github.com/BhookOuyang>

"""Transport layer for AuroraSNodeManager clipboard data.

Provides two optional, decoupled features that wrap the compact ``_aurora_c1``
clipboard payload produced by ``core.codec``:

  1. Encryption: PBKDF2-HMAC-SHA256 + AES-GCM (pure-Python, stdlib only).
     Reversible; the receiver must supply the correct password.
  2. Sharding: split a payload string into fixed-size chunks, each marked with
     an n/m header. The receiver collects chunks and reassembles the payload.

The two features are independent: either may be used alone or both together.

Layering (outermost -> innermost):

  shard  ``_aurora_s1`` -> encrypted ``_aurora_c2`` -> compact ``_aurora_c1``
"""
import base64
import hashlib
import json
import os
import time

from ..utils.translations import tr

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SHARD_MAGIC = "_aurora_s1"
SHARD_VERSION = 1
ENCRYPT_MAGIC = "_aurora_c2"
ENCRYPT_VERSION = 1
PBKDF2_ITERATIONS = 100000
SALT_LEN = 16
NONCE_LEN = 12
TAG_LEN = 16


def is_shard(data):
    """True if a parsed object is a shard chunk."""
    return isinstance(data, dict) and data.get(SHARD_MAGIC) == SHARD_VERSION


def is_encrypted(data):
    """True if a parsed object is an encrypted payload wrapper."""
    return isinstance(data, dict) and data.get(ENCRYPT_MAGIC) == ENCRYPT_VERSION


# ---------------------------------------------------------------------------
# Pure-Python AES (Rijndael) - encryption only (all that GCM/CTR need)
# ---------------------------------------------------------------------------
_SBOX = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
]

_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36]


def _xtime(a):
    a <<= 1
    if a & 0x100:
        a ^= 0x11b
    return a & 0xff


def _key_expansion(key):
    nk = len(key) // 4
    nr = {4: 10, 6: 12, 8: 14}[nk]
    w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
    for i in range(nk, 4 * (nr + 1)):
        temp = list(w[i - 1])
        if i % nk == 0:
            temp = temp[1:] + temp[:1]
            temp = [_SBOX[b] for b in temp]
            temp[0] ^= _RCON[(i // nk) - 1]
        elif nk > 6 and i % nk == 4:
            temp = [_SBOX[b] for b in temp]
        w.append([w[i - nk][j] ^ temp[j] for j in range(4)])
    return w, nr


def _add_round_key(state, w, rnd):
    for c in range(4):
        for r in range(4):
            state[r][c] ^= w[rnd * 4 + c][r]


def _sub_bytes(state):
    for r in range(4):
        for c in range(4):
            state[r][c] = _SBOX[state[r][c]]


def _shift_rows(state):
    for r in range(4):
        state[r] = state[r][r:] + state[r][:r]


def _mix_columns(state):
    for c in range(4):
        a0, a1, a2, a3 = (state[r][c] for r in range(4))
        state[0][c] = _xtime(a0) ^ _xtime(a1) ^ a1 ^ a2 ^ a3
        state[1][c] = a0 ^ _xtime(a1) ^ _xtime(a2) ^ a2 ^ a3
        state[2][c] = a0 ^ a1 ^ _xtime(a2) ^ _xtime(a3) ^ a3
        state[3][c] = _xtime(a0) ^ a0 ^ a1 ^ a2 ^ _xtime(a3)


def _aes_encrypt_block(block, key):
    """Encrypt a 16-byte block (bytes) with AES-128/192/256."""
    state = [[block[4 * c + r] for c in range(4)] for r in range(4)]
    w, nr = _key_expansion(key)
    _add_round_key(state, w, 0)
    for rnd in range(1, nr):
        _sub_bytes(state)
        _shift_rows(state)
        _mix_columns(state)
        _add_round_key(state, w, rnd)
    _sub_bytes(state)
    _shift_rows(state)
    _add_round_key(state, w, nr)
    out = bytearray(16)
    for r in range(4):
        for c in range(4):
            out[4 * c + r] = state[r][c]
    return bytes(out)


# ---------------------------------------------------------------------------
# AES-GCM mode (no AAD used)
# ---------------------------------------------------------------------------
_GF128_MASK = (1 << 128) - 1


def _gcm_mul(x, y):
    """Multiply two 128-bit field elements (GF(2^128), polynomial 0x87)."""
    res = 0
    for _ in range(128):
        if y & 1:
            res ^= x
        x <<= 1
        if x & (1 << 128):
            x ^= 0x87
        y >>= 1
    return res & _GF128_MASK


def _gcm_ghash(h, data):
    """GHASH over data (bytes, already padded to a multiple of 16)."""
    y = 0
    for i in range(0, len(data), 16):
        block = int.from_bytes(data[i:i + 16], "big")
        y = _gcm_mul(y ^ block, h)
    return y


def _aes_gcm_encrypt(key, nonce, plaintext):
    h = int.from_bytes(_aes_encrypt_block(bytes(16), key), "big")
    iv_int = int.from_bytes(nonce, "big")
    blocks = (len(plaintext) + 15) // 16
    keystream = b"".join(
        _aes_encrypt_block(((iv_int << 32) | (i + 1)).to_bytes(16, "big"), key)
        for i in range(blocks)
    )
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, keystream))

    pad = (-len(ciphertext)) % 16
    ghost_in = ciphertext + bytes(pad) + (len(ciphertext) * 8).to_bytes(8, "big")
    s = _gcm_ghash(h, ghost_in)
    j0 = _aes_encrypt_block((iv_int << 32 | 1).to_bytes(16, "big"), key)
    tag = (s ^ int.from_bytes(j0, "big")).to_bytes(TAG_LEN, "big")
    return ciphertext, tag


def _aes_gcm_decrypt(key, nonce, ciphertext, tag):
    h = int.from_bytes(_aes_encrypt_block(bytes(16), key), "big")
    iv_int = int.from_bytes(nonce, "big")
    blocks = (len(ciphertext) + 15) // 16
    keystream = b"".join(
        _aes_encrypt_block(((iv_int << 32) | (i + 1)).to_bytes(16, "big"), key)
        for i in range(blocks)
    )
    plaintext = bytes(a ^ b for a, b in zip(ciphertext, keystream))

    pad = (-len(ciphertext)) % 16
    ghost_in = ciphertext + bytes(pad) + (len(ciphertext) * 8).to_bytes(8, "big")
    s = _gcm_ghash(h, ghost_in)
    j0 = _aes_encrypt_block((iv_int << 32 | 1).to_bytes(16, "big"), key)
    expected = (s ^ int.from_bytes(j0, "big")).to_bytes(TAG_LEN, "big")
    if expected != tag:
        return None
    return plaintext


# ---------------------------------------------------------------------------
# Public encryption API (password -> reversible wrapper)
# ---------------------------------------------------------------------------
def _derive_key(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                               PBKDF2_ITERATIONS, dklen=32)


def encrypt_text(text, password):
    """Encrypt a text string into an ``_aurora_c2`` wrapper dict."""
    if not password:
        raise ValueError(tr("Password cannot be empty"))
    salt = os.urandom(SALT_LEN)
    nonce = os.urandom(NONCE_LEN)
    key = _derive_key(password, salt)
    ciphertext, tag = _aes_gcm_encrypt(key, nonce, text.encode("utf-8"))
    return {
        ENCRYPT_MAGIC: ENCRYPT_VERSION,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "tag": base64.b64encode(tag).decode("ascii"),
        "data": base64.b64encode(ciphertext).decode("ascii"),
    }


def decrypt_text(wrapper, password):
    """Decrypt an ``_aurora_c2`` wrapper back to the original text string."""
    try:
        salt = base64.b64decode(wrapper["salt"])
        nonce = base64.b64decode(wrapper["nonce"])
        tag = base64.b64decode(wrapper["tag"])
        ciphertext = base64.b64decode(wrapper["data"])
    except (KeyError, ValueError):
        raise ValueError(tr("Encrypted data format is invalid"))
    key = _derive_key(password, salt)
    plaintext = _aes_gcm_decrypt(key, nonce, ciphertext, tag)
    if plaintext is None:
        raise ValueError(tr("Incorrect password; cannot decrypt"))
    return plaintext.decode("utf-8")


# ---------------------------------------------------------------------------
# Sharding
# ---------------------------------------------------------------------------
def shard_text(text, size, extra_first=None):
    """Split ``text`` into chunks of at most ``size`` characters.

    Each chunk is a dict (``_aurora_s1``) carrying ``n``/``m`` plus a session
    ``token``. The first chunk additionally carries integrity meta plus any
    caller-supplied ``extra_first`` items (e.g. an ``encrypted`` flag).
    """
    if size < 1:
        raise ValueError(tr("Shard size must be greater than 0"))
    if not text:
        text = ""
    token = os.urandom(8).hex()
    m = max(1, (len(text) + size - 1) // size)
    chunks = []
    for i in range(m):
        chunk = {
            SHARD_MAGIC: SHARD_VERSION,
            "token": token,
            "n": i + 1,
            "m": m,
            "data": text[i * size:(i + 1) * size],
        }
        if i == 0:
            meta = {
                "ver": SHARD_VERSION,
                "size": len(text),
                "hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "created": time.time(),
                "encrypted": 0,
            }
            if extra_first:
                meta.update(extra_first)
            chunk.update(meta)
        chunks.append(chunk)
    return chunks


def chunk_to_text(chunk):
    """Serialize one chunk dict to its clipboard JSON string."""
    return json.dumps(chunk, separators=(",", ":"), ensure_ascii=False)


def assemble_chunks(chunks):
    """Reassemble shard chunks (any order) back into the full text string.

    Raises ValueError if chunks are missing or the payload fails integrity
    checks (size / sha256 recorded in the first chunk).
    """
    if not chunks:
        raise ValueError(tr("No shards to assemble"))
    first = chunks[0]
    m = first.get("m")
    if not m or m < 1:
        raise ValueError(tr("Missing shard metadata"))
    ordered = {}
    for chunk in chunks:
        n = chunk.get("n")
        if not n or n < 1 or n > m:
            raise ValueError(tr("Invalid shard number: {}").format(n))
        ordered[n] = chunk
    if len(ordered) != m:
        missing = [n for n in range(1, m + 1) if n not in ordered]
        raise ValueError(tr("Incomplete shards, missing: {}").format(missing))
    text = "".join(ordered[n].get("data", "") for n in range(1, m + 1))
    size = first.get("size")
    if size is not None and len(text) != size:
        raise ValueError(tr("Shard data length mismatch (expected {}, got {})").format(size, len(text)))
    digest = first.get("hash")
    if digest and hashlib.sha256(text.encode("utf-8")).hexdigest() != digest:
        raise ValueError(tr("Shard data verification failed (possibly corrupted in transit)"))
    return text


# ---------------------------------------------------------------------------
# Shard collector (receiver side, module-level singleton)
# ---------------------------------------------------------------------------
class ShardCollector:
    """Accumulates shard chunks keyed by session token (out-of-order safe)."""

    def __init__(self):
        self._sets = {}

    def feed(self, chunk):
        """Store one chunk. Returns a status dict for the operator.

        status in {"ok", "dup", "conflict"}; token/total/received included
        so the UI can render progress.
        """
        if not is_shard(chunk):
            return {"status": "invalid", "message": tr("Clipboard content is not a shard")}
        token = chunk.get("token")
        n = chunk.get("n")
        m = chunk.get("m")
        if not token or not n or not m:
            return {"status": "invalid", "message": tr("Incomplete shard info")}
        active = self.active_token()
        if active and active != token and not self.is_complete(active):
            return {"status": "conflict",
                    "message": tr("Shard from a different batch, ignored (current batch {}…)").format(active[:8])}
        if token not in self._sets:
            self._sets[token] = {
                "m": m,
                "chunks": {},
                "first": None,
            }
        record = self._sets[token]
        if record["m"] != m:
            return {"status": "invalid", "message": tr("Inconsistent shard total")}
        if n in record["chunks"]:
            return {"status": "dup", "message": tr("Shard {}/{} already received, skipped").format(n, m),
                    "token": token, "total": m,
                    "received": self._received(record)}
        if n == 1:
            record["first"] = chunk
        record["chunks"][n] = chunk
        return {"status": "ok", "message": tr("Received shard {}/{}").format(n, m),
                "token": token, "total": m,
                "received": self._received(record)}

    @staticmethod
    def _received(record):
        return len(record["chunks"])

    def active_token(self):
        for token, record in self._sets.items():
            if not self.is_complete(token):
                return token
        return None

    def is_complete(self, token):
        record = self._sets.get(token)
        if not record:
            return False
        return len(record["chunks"]) == record["m"]

    def status(self, token):
        record = self._sets.get(token)
        if not record:
            return {"m": 0, "received": 0, "indices": [], "encrypted": False,
                    "complete": False, "token": token}
        first = record["first"] or {}
        return {
            "m": record["m"],
            "received": len(record["chunks"]),
            "indices": sorted(record["chunks"]),
            "encrypted": bool(first.get("encrypted")),
            "complete": self.is_complete(token),
            "token": token,
        }

    def assemble(self, token):
        record = self._sets.get(token)
        if not record:
            raise ValueError(tr("No shard session"))
        return assemble_chunks([record["chunks"][n]
                                for n in range(1, record["m"] + 1)])

    def reset(self, token=None):
        if token is None:
            self._sets.clear()
        else:
            self._sets.pop(token, None)


collector = ShardCollector()


# ---------------------------------------------------------------------------
# Cross-operator session state (send side + pending payload)
# ---------------------------------------------------------------------------
_send_session = None          # {"token", "chunks": [...], "copied": set()}
_receiver_token = None        # token bound to the open receiver popup
_pending_payload = None       # an _aurora_c2 wrapper awaiting a password
_receiver_state = {"phase": None, "encrypted": False}  # "collecting"|"decrypt"|"done"


def set_receiver_phase(phase, encrypted=False):
    """Update the receiver UI phase (None/"decrypt"/"done")."""
    global _receiver_state
    _receiver_state = {"phase": phase, "encrypted": bool(encrypted)}


def receiver_phase():
    return _receiver_state.get("phase")


def receiver_encrypted():
    return bool(_receiver_state.get("encrypted"))


def has_receiver_ui():
    return (_receiver_token is not None
            or _receiver_state.get("phase") == "decrypt")


def open_send_session(chunks):
    """Register a new send-side shard session (replaces any previous one)."""
    global _send_session
    if not chunks:
        _send_session = None
        return None
    _send_session = {
        "token": chunks[0].get("token"),
        "chunks": list(chunks),
        "copied": set(),
    }
    return _send_session


def send_session():
    return _send_session


def mark_shard_copied(idx):
    if _send_session and 0 <= idx < len(_send_session["chunks"]):
        _send_session["copied"].add(idx)
        return True
    return False


def reset_send_session():
    global _send_session
    _send_session = None


def set_receiver_token(token):
    global _receiver_token
    _receiver_token = token


def receiver_token():
    return _receiver_token


def clear_receiver_token():
    global _receiver_token
    _receiver_token = None


def set_pending_payload(wrapper):
    global _pending_payload
    _pending_payload = wrapper


def clear_pending_payload():
    global _pending_payload
    _pending_payload = None


def pop_pending_payload():
    global _pending_payload
    wrapper = _pending_payload
    _pending_payload = None
    return wrapper