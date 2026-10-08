"""
compare_sync_async.py
Timing experiment: the same N searches against the synchronous server and the
asynchronous server, both with the same artificial --delay per request.

  (a) sync server, sync stub, requests one after another   ~ N x delay
  (b) async server, grpc.aio stub, asyncio.gather          ~ 1 x delay
  Extra rows (--extra, default 50 requests):
  (c) sync server, 10 worker threads, requests from threads ~ ceil(M/10) x delay
  (d) async server, asyncio.gather of M requests            ~ 1 x delay

  Lock check: 10 concurrent RentBook calls for B003 (a single copy) on each server;
  exactly one must succeed (RentalManager's lock, end to end).

Both servers are started inside this script, so only one command is needed:
    python compare_sync_async.py [--delay 0.5] [--n 10] [--extra 50]
"""

import argparse
import asyncio
import os
import time
from concurrent import futures

os.environ.setdefault("GRPC_VERBOSITY", "ERROR")   # hide harmless transport logs

import grpc

import rental_pb2
import rental_pb2_grpc
from async_server import create_server
from sync_server import build_server

TIMEOUT = 60
WORKERS = 10


def sync_sequential(port, n):
    with grpc.insecure_channel(f"localhost:{port}") as ch:
        stub = rental_pb2_grpc.RentalServiceStub(ch)
        t0 = time.perf_counter()
        for _ in range(n):
            stub.SearchBooks(rental_pb2.SearchRequest(keyword="system"), timeout=TIMEOUT)
        return time.perf_counter() - t0


def sync_threaded(port, m):
    with grpc.insecure_channel(f"localhost:{port}") as ch:
        stub = rental_pb2_grpc.RentalServiceStub(ch)
        t0 = time.perf_counter()
        with futures.ThreadPoolExecutor(max_workers=m) as pool:
            jobs = [pool.submit(stub.SearchBooks,
                                rental_pb2.SearchRequest(keyword="system"), timeout=TIMEOUT)
                    for _ in range(m)]
            for j in jobs:
                j.result()
        return time.perf_counter() - t0


async def async_gather(port, n):
    async with grpc.aio.insecure_channel(f"localhost:{port}") as ch:
        stub = rental_pb2_grpc.RentalServiceStub(ch)
        t0 = time.perf_counter()
        await asyncio.gather(*(stub.SearchBooks(rental_pb2.SearchRequest(keyword="system"),
                                                timeout=TIMEOUT) for _ in range(n)))
        return time.perf_counter() - t0


def sync_rent_race(port, k):
    """k threads rent the single copy of B003 at the same time."""
    with grpc.insecure_channel(f"localhost:{port}") as ch:
        stub = rental_pb2_grpc.RentalServiceStub(ch)
        with futures.ThreadPoolExecutor(max_workers=k) as pool:
            jobs = [pool.submit(stub.RentBook,
                                rental_pb2.BookRequest(student_id=f"S{3000 + i}", book_id="B003"),
                                timeout=TIMEOUT) for i in range(k)]
            res = [j.result() for j in jobs]
    return sum(1 for r in res if r.success), len(res)


async def async_rent_race(port, k):
    """k coroutines rent the single copy of B003 at the same time."""
    async with grpc.aio.insecure_channel(f"localhost:{port}") as ch:
        stub = rental_pb2_grpc.RentalServiceStub(ch)
        res = await asyncio.gather(*(stub.RentBook(
            rental_pb2.BookRequest(student_id=f"S{3000 + i}", book_id="B003"),
            timeout=TIMEOUT) for i in range(k)))
    return sum(1 for r in res if r.success), len(res)


async def run_async_part(delay, n, extra):
    server, port = await create_server(port=0, delay=delay)
    await server.start()
    try:
        await async_gather(port, 2)               # warm-up (connection setup)
        t_n = await async_gather(port, n)
        t_m = await async_gather(port, extra) if extra else None
    finally:
        await server.stop(grace=None)
    # lock check on a FRESH async server (B003 has exactly one copy again)
    server, port = await create_server(port=0, delay=delay)
    await server.start()
    try:
        race = await async_rent_race(port, 10)
    finally:
        await server.stop(grace=None)
    return t_n, t_m, race


def main():
    ap = argparse.ArgumentParser(description="Sync vs async gRPC timing")
    ap.add_argument("--delay", type=float, default=0.5, help="seconds per request on the server")
    ap.add_argument("--n", type=int, default=10, help="number of searches (main comparison)")
    ap.add_argument("--extra", type=int, default=50, help="requests for the extra rows (0 = skip)")
    a = ap.parse_args()

    # ---- synchronous part (runs outside the event loop) ----
    server, port = build_server(port=0, delay=a.delay, max_workers=WORKERS)
    server.start()
    try:
        sync_sequential(port, 2)                   # warm-up
        t_sync_seq = sync_sequential(port, a.n)
        t_sync_thr = sync_threaded(port, a.extra) if a.extra else None
    finally:
        server.stop(grace=None)
    server, port = build_server(port=0, delay=a.delay, max_workers=WORKERS)   # fresh data
    server.start()
    try:
        sync_race = sync_rent_race(port, 10)
    finally:
        server.stop(grace=None)

    # ---- asynchronous part ----
    t_async_n, t_async_m, async_race = asyncio.run(run_async_part(a.delay, a.n, a.extra))

    print(f"\nServer delay per request: {a.delay}s   (sync server: {WORKERS} worker threads)\n")
    print(f"{'Scenario':<58}{'Requests':>9}{'Time (s)':>10}")
    print("-" * 77)
    print(f"{'(a) sync stub, one after another':<58}{a.n:>9}{t_sync_seq:>10.2f}")
    print(f"{'(b) async stub, asyncio.gather':<58}{a.n:>9}{t_async_n:>10.2f}")
    print(f"\nSpeed-up (a)/(b): {t_sync_seq / t_async_n:.1f}x   "
          f"(ideal: sequential ~ {a.n * a.delay:.1f}s, concurrent ~ {a.delay:.1f}s)")
    if a.extra:
        print()
        print(f"{'(c) sync server, threaded clients (10 workers)':<58}{a.extra:>9}{t_sync_thr:>10.2f}")
        print(f"{'(d) async server, asyncio.gather (1 thread)':<58}{a.extra:>9}{t_async_m:>10.2f}")
        print(f"\nSpeed-up (c)/(d): {t_sync_thr / t_async_m:.1f}x")
    print("\nLock check: 10 concurrent RentBook calls for B003 (only 1 copy in stock)")
    print(f"  sync server  (10 threads): {sync_race[0]} of {sync_race[1]} succeeded")
    print(f"  async server (gather)    : {async_race[0]} of {async_race[1]} succeeded")
    ok = sync_race[0] == 1 and async_race[0] == 1
    print("  RESULT:", "OK, exactly one winner on each server" if ok else "PROBLEM: expected exactly 1")


if __name__ == "__main__":
    main()
