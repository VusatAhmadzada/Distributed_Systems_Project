# Distributed_Systems_HW 1
# University Textbook Rental Hub (INFT 6000, Homework 1)

## Files

| File | What it is |
|---|---|
| `models.py`, `book_catalog.py`, `rental_manager.py`, `sample_data.py` | OOP layer (no networking) |
| `demo.py`, `test_rental_hub.py` | local demo and 13 unit tests for the OOP layer |
| `rental.proto` | gRPC contract: one service, 5 unary RPCs |
| `rental_pb2.py`, `rental_pb2_grpc.py` | generated from `rental.proto`, do not edit by hand |
| `sync_server.py`, `sync_client.py` | synchronous gRPC server and client (`localhost:50051`) |
| `test_sync_grpc.py` | 19 end-to-end tests over the network |
| `async_server.py`, `async_client.py` | asynchronous gRPC server and client (`localhost:50052`) |
| `compare_sync_async.py` | timing: same searches on the sync and the async server |
| `test_async_grpc.py` | 18 end-to-end tests for the async server |
| `evidence/` | saved output of the async demo, the timing script and all tests |


## Setup

```
pip install -r requirements.txt
```

The generated files need `grpcio>=1.84.0` and `protobuf>=7.35.1`. If you get a version error on import, upgrade the packages or regenerate the stubs:

```
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. rental.proto
```

## Run

Local OOP demo (no gRPC):

```
python demo.py
```

Synchronous gRPC, two terminals:

```
python sync_server.py                # options: --port 50051 --delay 0 --workers 10
python sync_client.py                # options: --port 50051 --timeout 2
```

Try `python sync_server.py --delay 1`: every call now takes about a second, so the client visibly waits for each answer, and a `--timeout` below the delay gives DEADLINE_EXCEEDED. If no server is running the client prints an UNAVAILABLE message and exits.

Asynchronous gRPC, two terminals:

```
python async_server.py               # options: --port 50052 --delay 0
python async_client.py               # options: --port 50052 --timeout 5
```

Try `python async_server.py --delay 0.5`: the client's second demo sends 10 searches at once and all answers arrive after about 0.5 s.

Sync versus async timing (starts both servers itself, one terminal):

```
python compare_sync_async.py --delay 0.5 --n 10 --extra 50
```

## Tests

```
python -m unittest -v                    # all 50 tests
python -m unittest -v test_rental_hub    # OOP layer only (13)
python -m unittest -v test_sync_grpc     # sync gRPC (19), starts its own server on a free port
python -m unittest -v test_async_grpc    # async gRPC (18), starts its own server on a free port
```

## Structure

```
client -> gRPC / protobuf -> sync_server.py (RentalServicer) or async_server.py (AsyncRentalServicer)
                                  -> RentalManager -> BookCatalog (OOP layer)
                                  -> response message -> client
```

The servicer creates one catalog and one manager when the server starts. Handlers only copy fields between messages and the OOP objects; the rental rules live in `RentalManager`.
