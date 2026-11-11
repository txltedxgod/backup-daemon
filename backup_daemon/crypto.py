import gzip
import os
import shutil
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_SIZE = 12
_MIN_ENCRYPTED_SIZE = _NONCE_SIZE + 16  # nonce + 128-bit GCM auth tag


def _parse_aes_key(key_hex: str) -> bytes:
    key = bytes.fromhex(key_hex)
    if len(key) not in (16, 24, 32):
        raise ValueError("AES key must be 16, 24, or 32 bytes (32, 48, or 64 hex chars)")
    return key


def compress_file(src_path: Path) -> Path:
    out_path = src_path.with_suffix(src_path.suffix + ".gz")
    with open(src_path, "rb") as f_in, gzip.open(out_path, "wb", compresslevel=9) as f_out:
        shutil.copyfileobj(f_in, f_out)
    src_path.unlink()
    return out_path


def encrypt_file(src_path: Path, key_hex: str) -> Path:
    key = _parse_aes_key(key_hex)
    aesgcm = AESGCM(key)
    nonce = os.urandom(_NONCE_SIZE)

    data = src_path.read_bytes()
    encrypted = aesgcm.encrypt(nonce, data, None)

    out_path = src_path.with_suffix(src_path.suffix + ".enc")
    with open(out_path, "wb") as f:
        f.write(nonce)
        f.write(encrypted)

    src_path.unlink()
    return out_path


def decrypt_file(src_path: Path, key_hex: str) -> Path:
    key = _parse_aes_key(key_hex)
    payload = src_path.read_bytes()
    if len(payload) < _MIN_ENCRYPTED_SIZE:
        raise ValueError("Encrypted payload is truncated or invalid")

    nonce = payload[:_NONCE_SIZE]
    ciphertext = payload[_NONCE_SIZE:]
    plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)

    out_path = (
        src_path.with_suffix("")
        if src_path.suffix == ".enc"
        else src_path.with_suffix(src_path.suffix + ".dec")
    )
    out_path.write_bytes(plaintext)
    return out_path
