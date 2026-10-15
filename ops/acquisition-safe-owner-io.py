#!/usr/bin/env python3
"""Safe bounded root reads from an untrusted, worker-controlled job directory.

Open every path component as O_DIRECTORY|O_NOFOLLOW. Pin the final directory
descriptor once and open only fixed-name regular members relative to that
descriptor. No symlinks, FIFOs, devices, ancestor redirects or unbounded reads.
This module never creates files, grants authority, contacts a provider or
starts a worker.
"""
from __future__ import annotations
from contextlib import contextmanager
import os
from pathlib import Path
import re
import stat

JOB_ROOT=Path("/srv/ghostmesh/workspaces/runs/reasonpack-jobs")
HEXDIGEST=re.compile(r"^[0-9a-f]{64}$")
DIR_FLAGS=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC
FILE_FLAGS=os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC

def refuse(message): raise ValueError(message)

@contextmanager
def _open_tree_dir(root,job_id):
    """Private directory walker, injectable root solely for offline tests."""
    if not isinstance(root,Path) or not root.is_absolute():
        refuse("unsafe directory anchor")
    fd=os.open("/",DIR_FLAGS)
    try:
        for component in (*root.parts[1:],job_id):
            next_fd=os.open(component,DIR_FLAGS,dir_fd=fd)
            os.close(fd)
            fd=next_fd
        info=os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode):
            refuse("job identity does not address a directory")
        yield fd
    finally:
        os.close(fd)

@contextmanager
def opened_job(job_id):
    """Only the fixed reviewed job root is accepted by the privileged caller."""
    if not isinstance(job_id,str) or not HEXDIGEST.fullmatch(job_id):
        refuse("unsafe root job locator")
    with _open_tree_dir(JOB_ROOT,job_id) as fd:
        yield fd

def read_regular_member(job_fd,member,max_bytes):
    """Read bounded bytes from one fixed named regular file within pinned job."""
    if member not in {"admission.json","supervision.json",
                       "launch-grant.json","launch-grant.sig"}:
        refuse("unapproved member of signed acquisition job")
    if not isinstance(max_bytes,int) or not (64<=max_bytes<=65536):
        refuse("invalid bounded job member ceiling")
    fd=os.open(member,FILE_FLAGS,dir_fd=job_fd)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or not (1<=info.st_size<=max_bytes):
            refuse("job member is nonregular, empty or oversized: "+member)
        chunks=[]
        used=0
        while used<=max_bytes:
            piece=os.read(fd,min(65536,max_bytes-used+1))
            if not piece:break
            used+=len(piece)
            if used>max_bytes:
                refuse("job member expanded while being read: "+member)
            chunks.append(piece)
        result=b"".join(chunks)
        if len(result)!=info.st_size:
            refuse("job member changed during bounded read: "+member)
        if os.fstat(fd).st_size!=info.st_size:
            refuse("job member changed size during bounded read: "+member)
        return result
    finally:
        os.close(fd)
