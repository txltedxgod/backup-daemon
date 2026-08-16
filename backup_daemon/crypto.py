import gzip
import os
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def compress_file(src_path: Path) -> Path:
    out_path = src_path.with_suffix(src_path.suffix + ".gz")
    with open(src_path, "rb") as f_in:
        with gzip.open(out_path, "wb", compresslevel=9) as f_out:
            f_out.writelines(f_in)
    src_path.unlink()
    return out_path


def encrypt_file(src_path: Path, key_hex: str) -> Path:
    key = bytes.fromhex(key_hex)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)

    data = src_path.read_bytes()
    encrypted = aesgcm.encrypt(nonce, data, None)

    out_path = src_path.with_suffix(src_path.suffix + ".enc")
    with open(out_path, "wb") as f:
        f.write(nonce)
        f.write(encrypted)

    src_path.unlink()
    return out_path
