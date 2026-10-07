# Handoff to Person 4

## What Person 3 added (no existing file was changed)
| File | Purpose |
|---|---|
| `async_server.py` | `AsyncRentalServicer`, `grpc.aio.server()`, port 50052, `--delay` uses `await asyncio.sleep` |
| `async_client.py` | Demo 1: awaited calls. Demo 2: 10 searches with `asyncio.gather` |
| `compare_sync_async.py` | Timing sync vs async (starts both servers itself) |
| `test_async_grpc.py` | 18 tests; whole project: 50 tests, all pass |
| `evidence/` | `async_server_output.txt`, `async_client_output.txt`, `compare_sync_async_output.txt`, `unittest_all_output.txt` |
| `uml/class_diagram_async.*` | UML class diagram with both servicers |

Documents: `Person3_Section_5_Async_gRPC.docx/.pdf` (report section 5) and `Person3_Slides_5_6.pptx` (slide 5 async code, slide 6 demo and timing).

## Commands (two terminals)
```
pip install -r requirements.txt
python async_server.py --delay 0.5      # terminal 1
python async_client.py                  # terminal 2
python compare_sync_async.py --delay 0.5
python -m unittest -v                   # 50 tests
```

## Also included
- `async_client.py` has a "still working" ticker task running during Demo 2 (the client stays responsive).
- `compare_sync_async.py` ends with a lock check: 10 concurrent RentBook calls for B003 on each server, exactly 1 succeeds.

## Measured numbers (delay 0.5 s per request)
| Scenario | Requests | Time |
|---|---|---|
| sync client, one after another | 10 | 5.01 s |
| async client, asyncio.gather | 10 | 0.51 s |
| sync server 10 workers, threaded clients | 50 | 2.52 s |
| async server, asyncio.gather | 50 | 0.51 s |

These were measured once on the machine that built the files. Re-run `compare_sync_async.py` on your own computer; if your numbers differ, update the table in report section 5 and the chart on slide 6.

## Still to do for the final package
- Report: title page with team names and IDs, section 6 (conclusion and lessons learned), merge sections 1 to 5 into one PDF of at least 8 pages. Sections 3 to 5 refer to "Person 1 / 2 / 3" and should be changed to real names or to "the team".
- Slides: slide 1 (title), 2 (problem and OOP architecture), 7 (challenges), 8 (Q&A). Slides 3 and 4 are from Person 2, slides 5 and 6 from Person 3.
- Evidence: screenshots of both terminals side by side, and the video recording of the demo.

## Lessons learned (material for section 6)
- Calling `time.sleep` inside an `async def` handler silently removes all concurrency; use `await asyncio.sleep`.
- The synchronous part of the timing script must run outside the event loop, because a blocking stub call would freeze an async server living in the same loop.
- Tests use port 0 so they never collide with a running server on 50051 or 50052.
- `unittest.IsolatedAsyncioTestCase` gives every test its own event loop and a fresh server.
- Port binding: `add_insecure_port` returns 0 on failure, so the servers raise a clear error if the port is busy.
