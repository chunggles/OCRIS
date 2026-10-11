"""
Encryption at rest for uploaded scans and backup files.

A file is written as MAGIC followed by chunks of [4-byte length][Fernet token], so a large file
is never held in memory whole. The key comes from DATA_ENCRYPTION_KEY in .env; the first key
encrypts and every key can decrypt, which makes rotating keys possible. Files written before
encryption was switched on carry no MAGIC and are read as they are.
"""
import struct
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings

MAGIC = b'OCRISENC2'
CHUNK_SIZE = 1024 * 1024
LENGTH = struct.Struct('>I')


class CryptoError(Exception):
    """The file cannot be encrypted or decrypted. The message is safe to show."""


def _keys():
    return [k for k in getattr(settings, 'DATA_ENCRYPTION_KEYS', []) if k]


def enabled():
    return bool(_keys())


def _cipher():
    keys = _keys()
    if not keys:
        raise CryptoError('This file is encrypted, but DATA_ENCRYPTION_KEY is not set on the server.')
    return MultiFernet([Fernet(k) for k in keys])


def is_encrypted(path):
    with open(path, 'rb') as f:
        return f.read(len(MAGIC)) == MAGIC


def encrypt_chunks(chunks, out):
    """Write the byte strings in `chunks` to the open binary file `out`, encrypted."""
    keys = _keys()
    if not keys:
        raise CryptoError('DATA_ENCRYPTION_KEY is not set on the server.')
    fernet = Fernet(keys[0])
    out.write(MAGIC)
    buffer = bytearray()
    written = 0

    def flush(data):
        token = fernet.encrypt(bytes(data))
        out.write(LENGTH.pack(len(token)) + token)

    for chunk in chunks:
        buffer += chunk
        while len(buffer) >= CHUNK_SIZE:
            flush(buffer[:CHUNK_SIZE])
            del buffer[:CHUNK_SIZE]
            written += 1
    if buffer or not written:   # an empty file still gets one (empty) chunk
        flush(buffer)


def _decrypt_chunks(f):
    cipher = _cipher()
    while True:
        header = f.read(LENGTH.size)
        if not header:
            return
        if len(header) < LENGTH.size:
            raise CryptoError('The encrypted file is damaged.')
        token = f.read(LENGTH.unpack(header)[0])
        try:
            yield cipher.decrypt(token)
        except InvalidToken:
            raise CryptoError('The file could not be decrypted: the key is wrong or the file is damaged.')


def iter_plain(path, size=CHUNK_SIZE):
    """The content of a stored file as byte strings, decrypting it if it is encrypted."""
    with open(path, 'rb') as f:
        if f.read(len(MAGIC)) == MAGIC:
            yield from _decrypt_chunks(f)
            return
        f.seek(0)
        while chunk := f.read(size):
            yield chunk


def read_plain(path):
    return b''.join(iter_plain(path))


def encrypt_file(path):
    """Encrypt a plain file in place. Returns False if it was already encrypted."""
    path = Path(path)
    if is_encrypted(path):
        return False
    temp = path.with_name(path.name + '.enc-tmp')
    try:
        with open(path, 'rb') as src, open(temp, 'wb') as out:
            encrypt_chunks(iter(lambda: src.read(CHUNK_SIZE), b''), out)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return True


def decrypt_to(path, target):
    with open(target, 'wb') as out:
        for chunk in iter_plain(path):
            out.write(chunk)
