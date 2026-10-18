"""
The audit file (AUDIT_LOG_FILE) as a hash chain. Each line holds one entry plus `prev`, the hash
of the line before it, and `hash`, the SHA-256 of the line itself without `hash`. Changing,
inserting, moving or deleting a line breaks the chain from there, which verify() reports. The
hash of each entry is also stored with its copy in MongoDB, so a file that is cut short or
replaced shows too.

A line left half-written by a crash is passed over: the next line follows the last whole line and
records the half line's digest as `cut`, so the chain stays whole and verify() accepts that one
line, but not one changed, removed or added later.

This makes a change visible, not impossible: someone who can rewrite both the file and the
database can recompute the chain. Copy the file to a log service or a machine the server cannot
write to for that.
"""
import hashlib
import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path

GENESIS = ''              # the `prev` of the first chained line
TAIL_CHUNK = 8192         # bytes read at a time from the end of the file to find its last line
_thread_lock = threading.Lock()


def _digest(line):
    """SHA-256 of a line's fields (everything but `hash`), written in one fixed form."""
    canonical = json.dumps(line, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _text_digest(raw):
    """SHA-256 of a line that cannot be read, as the bytes in the file without surrounding whitespace."""
    return hashlib.sha256(raw.strip()).hexdigest()


@contextmanager
def _locked(path):
    """One writer at a time, across threads and server processes, so two lines never share a `prev`."""
    with _thread_lock, open(f'{path}.lock', 'a+b') as lock:
        if os.name == 'nt':
            import msvcrt
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)   # retries for up to 10 seconds
            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _chain_end(path):
    """
    Where the next line joins the file, read from its end: (the `hash` of the last whole line, or
    GENESIS before the chain began; the last line when a crash left it half-written, else None;
    whether the file ends in the middle of a line). Lines that cannot be read are passed over.
    """
    try:
        f = open(path, 'rb')
    except FileNotFoundError:
        return GENESIS, None, False
    with f:
        f.seek(0, os.SEEK_END)
        pos, rest = f.tell(), b''
        cut, mid_line, at_end = None, False, True
        while pos > 0:
            step = min(TAIL_CHUNK, pos)
            pos -= step
            f.seek(pos)
            pieces = (f.read(step) + rest).split(b'\n')
            rest = pieces.pop(0) if pos else b''   # may go on in the part before
            for raw in reversed(pieces):
                end_piece, at_end = at_end, False   # the piece after the last newline: a line not finished
                if end_piece:
                    mid_line = bool(raw)
                if not raw.strip():
                    continue
                try:
                    return json.loads(raw).get('hash') or GENESIS, cut, mid_line
                except (ValueError, AttributeError):
                    if end_piece:
                        cut = raw
        return GENESIS, cut, mid_line


def _numbered_lines(path):
    """(line number, bytes) for each line of the file; nothing for a missing file."""
    try:
        with open(path, 'rb') as f:
            yield from enumerate(f, 1)
    except FileNotFoundError:
        return


def append(path, entry):
    """
    Append `entry` (JSON-ready: plain dicts, lists, text and numbers) as the next line of the
    chain and return its hash. Nothing is written for os.devnull, as in the tests.
    """
    if str(path) == os.devnull:
        return None
    path = Path(path)
    with _locked(path):
        prev, cut, mid_line = _chain_end(path)
        line = {**entry, 'prev': prev}
        if cut is not None:
            line['cut'] = _text_digest(cut)   # the half line a crash left just before this one
        line['hash'] = _digest(line)
        # a line cut off by a crash is ended first, so the new entry stays on a line of its own
        text = ('\n' if mid_line else '') + json.dumps(line, ensure_ascii=False) + '\n'
        with open(path, 'a', encoding='utf-8', newline='\n') as f:
            f.write(text)
    return line['hash']


def verify(path, stored_hashes=()):
    """
    Check the chain of the file at `path` against the hashes the database holds. Returns:
      entries    lines checked as part of the chain
      unchained  lines from before the chain began (written by an older OCRIS), not checkable
      problems   [(line number, what is wrong)]
      cut_off    line numbers of lines a crash left half-written: recorded by the line after them,
                 or the last line of the file, which the next entry will record
      missing    hashes in the database whose line is not in the file
      extra      entries in the file that the database does not hold, as {line, action, user, timestamp}
    """
    problems, cut_off, seen = [], [], {}   # seen: hash -> where and what the entry is
    entries = unchained = 0
    prev = GENESIS
    unread = None   # (line number, digest) of a line that cannot be read, until the next line says what it is
    for number, raw in _numbered_lines(path):
        if not raw.strip():
            continue
        try:
            line = json.loads(raw)
            stored = line.pop('hash', None)
        except (ValueError, AttributeError):
            if unread:
                problems.append((unread[0], 'cannot be read as an entry'))
            unread = (number, _text_digest(raw), raw.endswith(b'\n'))
            continue
        cut = line.get('cut') if stored is not None else None
        if unread and cut == unread[1]:
            cut_off.append(unread[0])
        elif unread:
            problems.append((unread[0], 'cannot be read as an entry'))
        elif cut is not None:
            problems.append((number, 'follows a line left half-written by a crash, but that line was removed or changed'))
        unread = None
        if stored is None:
            if entries:
                problems.append((number, 'has no hash, so it was added or rewritten after the chain began'))
            else:
                unchained += 1
            continue
        if line.get('prev') != prev:
            problems.append((number, 'does not follow the line before it: a line was removed, added or moved here'))
        if _digest(line) != stored:
            problems.append((number, 'was changed after it was written'))
        prev = stored
        entries += 1
        seen[stored] = {'line': number, **{key: line.get(key) for key in ('action', 'user', 'timestamp')}}
    if unread and not unread[2]:   # the last line, unfinished: a crash, until the next entry records it
        cut_off.append(unread[0])
    elif unread:
        problems.append((unread[0], 'cannot be read as an entry'))
    in_db = set(stored_hashes)
    return {
        'entries': entries,
        'unchained': unchained,
        'problems': problems,
        'cut_off': cut_off,
        'missing': [h for h in stored_hashes if h not in seen],
        'extra': [summary for h, summary in seen.items() if h not in in_db],
    }
