# University Textbook Rental Hub (INFT 6000, Homework 1)

Part 1 (OOP layer) and Part 2 (Protocol Buffers + synchronous gRPC). The asynchronous part is still to do, see `HANDOFF_PERSON3.md`.

## Files

| File | What it is |
|---|---|
| `models.py`, `book_catalog.py`, `rental_manager.py`, `sample_data.py` | OOP layer (no networking) |
| `demo.py`, `test_rental_hub.py` | local demo and 13 unit tests for the OOP layer |
| `rental.proto` | gRPC contract: one service, 5 unary RPCs |
| `rental_pb2.py`, `rental_pb2_grpc.py` | generated from `rental.proto`, do not edit by hand |
| `sync_server.py`, `sync_client.py` | synchronous gRPC server and client (`localhost:50051`) |
| `test_sync_grpc.py` | 19 end-to-end tests over the network |

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

## Tests

```
python -m unittest -v                    # all 32 tests
python -m unittest -v test_rental_hub    # OOP layer only (13)
python -m unittest -v test_sync_grpc     # gRPC (19), starts its own server on a free port
```

## Structure

```
client -> gRPC / protobuf -> sync_server.py (RentalServicer)
                                  -> RentalManager -> BookCatalog (OOP layer)
                                  -> response message -> client
```

The servicer creates one catalog and one manager when the server starts. Handlers only copy fields between messages and the OOP objects; the rental rules live in `RentalManager`.
