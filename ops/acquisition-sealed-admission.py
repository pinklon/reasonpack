#!/usr/bin/env python3
"""Immutable per-attempt admission handoff from the signed-grant parent.

Linux memfd with enforced F_SEAL_WRITE/GROW/SHRINK/SEAL. This carries the
EXACT bytes validated by the external signature to the downloader child,
eliminating a re-read of worker-writable job metadata.
"""
from __future__ import annotations
import fcntl
import os
import stat

MAX_BYTES=40_000
SEALS=(fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|
       fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL)

def reject(msg):raise ValueError(msg)

def seal_admission(raw):
    if not isinstance(raw,bytes) or not (2<=len(raw)<=MAX_BYTES):
        reject("approved admission byte count invalid")
    if not hasattr(os,"memfd_create") or not hasattr(os,"MFD_ALLOW_SEALING"):
        reject("immutable admission FD requires Linux memfd seals")
    fd=os.memfd_create("reasonpack-signed-admission",
        os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
    try:
        if os.write(fd,raw)!=len(raw):
            reject("short immutable admission write")
        fcntl.fcntl(fd,fcntl.F_ADD_SEALS,SEALS)
        assert_sealed(fd)
        os.lseek(fd,0,os.SEEK_SET)
        return fd
    except BaseException:
        os.close(fd)
        raise

def assert_sealed(fd):
    if not isinstance(fd,int) or fd<0:reject("admission file descriptor unavailable")
    info=os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or not (2<=info.st_size<=MAX_BYTES):
        reject("admission FD not a bounded sealed memory file")
    observed=fcntl.fcntl(fd,fcntl.F_GET_SEALS)
    if observed & SEALS != SEALS:reject("admission memory descriptor writable or unsealed")
    return info.st_size

def read_sealed_admission(fd):
    size=assert_sealed(fd)
    os.lseek(fd,0,os.SEEK_SET)
    raw=os.read(fd,size+1)
    if len(raw)!=size:reject("sealed admission bytes truncated")
    return raw
