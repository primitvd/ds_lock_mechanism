# DS Lock Mechanism

A scalable framework for multi-server / multi-client file locking built using Python and gRPC.
This project implements a lock server that coordinates access to shared resources (e.g., files, jobs, critical sections) across distributed clients, ensuring only one client holds a lock at a time.

The goal of this project is to provide a simple distributed lock service, where clients can request a lock by name and the server grants/revokes locks safely.

## Overview

In distributed systems, when multiple clients or services access the same resource (e.g., file, task queue, transaction), concurrent operations can lead to data corruption or race conditions.
A lock mechanism lets clients request exclusive access to resources — the server grants the lock to one client at a time, and releases it when done.

This repository implements that concept using:

- gRPC for client-server communication

- Protocol Buffers (.proto) for defining lock RPCs

- Python for both client and server implementations

## Architecture
```
+---------------------+            +---------------------+
|     Client 1        |            |     Client N        |
| (Requests locks)    |            | (Requests locks)    |
+---------------------+            +---------------------+
            \                             /
             \----------- gRPC -----------/
                          |
                          v
                +----------------------+
                |   Lock Server        |
                | (grants/releases     |
                |  resource locks)     |
                +----------------------+
```

- Server (server.py) — Listens for lock requests from clients.

- Client (client.py) — Sends lock acquisition/release requests.

- lock.proto — Protocol definitions used by gRPC and auto-generated Python stubs.

## Getting Started
### Prerequisites

Make sure you have:

- Python 3.8+

- grpcio, grpcio-tools

**Install dependencies:**

`pip install -r requirements.txt`
## Compiling Protocol Buffers

Before running the server/client you must generate Python gRPC code:
```
python -m grpc_tools.protoc \
  -I. --python_out=. --grpc_python_out=. lock.proto
```
This creates:

-  lock_pb2.py

-  lock_pb2_grpc.py

## Running the Lock Server

Start the server:

`python server.py`

By default the server listens on a configurable host/port.

## Using the Client

Example usage in client.py:

```
from lock_pb2 import LockRequest
from lock_pb2_grpc import LockServiceStub
import grpc

channel = grpc.insecure_channel('localhost:50051')
client = LockServiceStub(channel)

# request lock
resp = client.Acquire(LockRequest(resource="my_file.txt"))

# do work once lock acquired
# ...

# release lock
client.Release(LockRequest(resource="my_file.txt"))
```
## Test Cases

The test_cases/ folder contains example scenarios for verifying that:

- Multiple clients requesting the same lock are queued correctly

- Locks are held exclusively

- Server responds to release requests

## How It Works

This project uses a central lock manager:

1. Client sends Acquire(LockName) RPC

2. Server checks if lock is free

3. If free → grant it; otherwise queue until available

4. Client sends Release(LockName) when done

This is a basic distributed locking pattern similar to what’s used in many distributed systems and distributed filesystems to ensure mutual exclusion.

## Features

- Distributed lock server (single source of truth)
- Multiple clients can coordinate locks
- Uses scalable gRPC protocol
- Lock expiration / timeout
- Retry/backoff strategies
- High availability (clustered lock servers)

📝 License

This project is released under the MIT License — see LICENSE file for details.
