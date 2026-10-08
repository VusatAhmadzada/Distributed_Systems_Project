# Handoff to Person 3: Asynchronous gRPC

Build on what exists. Do not rewrite the OOP classes and do not change `rental.proto`.

## Reuse unchanged
- `models.py`, `book_catalog.py`, `rental_manager.py`, `sample_data.py`
- `rental.proto`, `rental_pb2.py`, `rental_pb2_grpc.py` (the same service works for both servers)
- from `sync_server.py`: `book_to_pb`, `rental_to_pb`, `result_to_pb`, `build_server` (importing it does not start anything)
- `requirements.txt` (`grpc.aio` is part of `grpcio`, nothing new to install)

## New files
| File | Content |
|---|---|
| `async_server.py` | `AsyncRentalServicer` with `async def` handlers for the same 5 RPCs. It creates the catalog and manager once and calls the OOP methods directly (no `await`, they are fast). `--delay` uses `await asyncio.sleep(delay)`, **never `time.sleep`**, which would block the event loop and remove all concurrency. Server: `grpc.aio.server()`, `add_insecure_port("localhost:50052")` (different port from the sync server), `await server.start()`, `await server.wait_for_termination()`. Also a `create_server(port, delay)` helper (port 0 allowed) for tests. |
| `async_client.py` | `grpc.aio.insecure_channel`. Demo 1: a few awaited calls (rent, out of stock B004, unknown B999, stock check, active rentals). Demo 2: 10 searches with `asyncio.gather` (the main demo). Each call has `timeout=`, errors caught as `grpc.aio.AioRpcError` (UNAVAILABLE / DEADLINE_EXCEEDED messages as in `sync_client.py`). |
| `compare_sync_async.py` | Timing script. Starts a sync and an async server in the same process with the same `--delay` (e.g. 0.5), then runs N = 10 searches: (a) sync stub, one after another; (b) async stub, `asyncio.gather`. Prints both times and the speed-up. Optional extra row: 50 requests from threads against the sync server (10 workers) vs `gather` of 50 on the async server. |
| `test_async_grpc.py` | See below. |

## What to demonstrate
Mainly `SearchBooks` (read-only, safe to run in parallel). Also `CheckStock` and a concurrent `RentBook` test (many students, last copy of B003).

```
sync:   request 1 -> wait -> response, request 2 -> wait -> response ...   ~ N x delay
async:  request 1 \
        request 2  >-- in flight together, answers arrive together         ~ 1 x delay
        request 3 /
```

Expected result with `--delay 0.5`, 10 searches (measured on a prototype): sync sequential about 5.0 s, async gather about 0.5 s. Be accurate in the report: a thread-pool sync server can also serve parallel clients (50 threaded clients on 10 workers took about 2.5 s in the prototype), but it is limited by the pool size and by threads; the async server handled 50 in about 0.5 s on one thread.

## Tests (`test_async_grpc.py`, `unittest.IsolatedAsyncioTestCase`, server on port 0)
1. successful rental and stock decrease
2. out of stock (B004) and unknown book (B999)
3. search (case-insensitive) and stock check, including unknown book
4. active rentals and return
5. 10 concurrent searches all return correct results
6. concurrent timing: with `--delay 0.3`, 10 gathered searches finish in well under 10 x 0.3 s (use a loose limit, for example < 1.5 s)
7. 20 concurrent `RentBook` for the last copy of B003: exactly 1 success
8. DEADLINE_EXCEEDED with a short timeout and a long delay

Run: `python -m unittest -v test_async_grpc` and `python -m unittest -v` (all tests).

## Evidence to save (folder `evidence/`, text or screenshots)
- `async_server` and `async_client` terminals side by side
- output of `compare_sync_async.py` (copy the numbers into the report)
- output of `python -m unittest -v`

## Report (about 2 pages, section 5 "Asynchronous gRPC")
- why async: one thread, `await` gives control back while waiting
- short snippet of one `async def` handler and of `asyncio.gather`
- timing table sync vs async, with the delay and N used
- one honest paragraph: when async helps (many waiting requests) and that the OOP code is shared, protected by the existing lock
- slides: 1 to 2 (code snippet + timing chart/table)

## Hand over to Person 4
Final code files, the test output, evidence folder, report section and slides, the exact commands to run (two terminals), the measured numbers, and any known problems.

Realistic time: about 6 to 8 hours.
