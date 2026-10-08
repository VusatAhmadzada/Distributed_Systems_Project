"""
async_client.py
Asynchronous client for the Textbook Rental Hub (grpc.aio + asyncio).

Demo 1: a few awaited calls, one after another (like sync_client.py).
Demo 2: 10 student searches sent at the same time with asyncio.gather,
while a small ticker task keeps printing "still working" (the client is not frozen).

Run (async_server.py must be running):
    python async_client.py [--port 50052] [--timeout 5]
"""

import argparse
import asyncio
import sys
import time

import grpc

import rental_pb2
import rental_pb2_grpc


class ServerUnavailable(Exception):
    """Raised by call() when the server cannot be reached."""


async def call(label, rpc, request, timeout):
    """Await one unary RPC with a deadline. Returns the response, or None on a
    handled error. Raises ServerUnavailable when the server is down."""
    try:
        return await rpc(request, timeout=timeout)
    except grpc.aio.AioRpcError as err:
        code = err.code()
        if code == grpc.StatusCode.UNAVAILABLE:
            print(f"  [UNAVAILABLE] {label}: cannot reach the server. "
                  f"Is async_server.py running on the right port?")
            raise ServerUnavailable() from err
        if code == grpc.StatusCode.DEADLINE_EXCEEDED:
            print(f"  [DEADLINE_EXCEEDED] {label}: no answer within {timeout}s.")
        else:
            print(f"  [{code.name}] {label}: {err.details()}")
        return None


def show_rental(r):
    status = "SUCCESS" if r.success else "FAILED "
    extra = f" (rental {r.rental_id}, stock left {r.remaining_stock})" if r.success else ""
    print(f"  [{status}] {r.message}{extra}")


async def demo_sequential(stub, timeout):
    """Demo 1: awaited calls. Each `await` waits for its answer, but the event
    loop is free to do other work meanwhile."""
    print("=== Demo 1: awaited calls, one after another ===")

    print("1) Successful rental (S1001 rents B001):")
    r = await call("RentBook", stub.RentBook,
                   rental_pb2.BookRequest(student_id="S1001", book_id="B001"), timeout)
    if r:
        show_rental(r)
    rental_id = r.rental_id if r else ""

    print("\n2) Out-of-stock book (B004):")
    r = await call("RentBook", stub.RentBook,
                   rental_pb2.BookRequest(student_id="S1001", book_id="B004"), timeout)
    if r:
        show_rental(r)

    print("\n3) Unknown book (B999):")
    r = await call("RentBook", stub.RentBook,
                   rental_pb2.BookRequest(student_id="S1001", book_id="B999"), timeout)
    if r:
        show_rental(r)

    print("\n4) Stock check:")
    for book_id in ("B001", "B999"):
        r = await call("CheckStock", stub.CheckStock,
                       rental_pb2.StockRequest(book_id=book_id), timeout)
        if r:
            note = "" if r.found else "  (book does not exist)"
            print(f"  {r.book_id}: stock = {r.stock}{note}")

    print("\n5) Active rentals (all students):")
    r = await call("ListActiveRentals", stub.ListActiveRentals,
                   rental_pb2.RentalsRequest(), timeout)
    if r:
        for x in r.rentals:
            print(f"  {x.rental_id}: student {x.student_id} has {x.book_id} ({x.price:.2f} AZN)")

    if rental_id:   # give the copy back so Demo 2 starts from the same state
        r = await call("ReturnBook", stub.ReturnBook,
                       rental_pb2.ReturnRequest(rental_id=rental_id), timeout)
        if r:
            print("\n6) Return the book:")
            show_rental(r)


SEARCH_KEYWORDS = ["algorithms", "systems", "database", "networking", "operating",
                   "concepts", "introduction", "computer", "distributed", "design"]


async def one_search(stub, student_no, keyword, timeout, t0):
    """One student's search. Returns (student_no, keyword, number_of_books)."""
    resp = await call(f"SearchBooks('{keyword}')", stub.SearchBooks,
                      rental_pb2.SearchRequest(keyword=keyword), timeout)
    found = len(resp.books) if resp else -1
    print(f"  [{time.perf_counter() - t0:5.2f}s] student {student_no:2d} "
          f"searched '{keyword}' -> {found} book(s)")
    return student_no, keyword, found


async def ticker(interval=0.1):
    """Background task: prints a dot-line every `interval` seconds. If the client
    were blocked, the ticks would stop; they keep coming while requests are in flight."""
    n = 0
    try:
        while True:
            await asyncio.sleep(interval)
            n += 1
            print(f"  ... still working (tick {n})")
    except asyncio.CancelledError:
        print(f"  ... ticker stopped after {n} ticks")
        raise


async def demo_concurrent(stub, timeout):
    """Demo 2: 10 searches in flight together. asyncio.gather starts all the
    coroutines, they all send their request right away, and the answers come back
    together. Total time is about ONE round trip, not ten."""
    print("\n=== Demo 2: 10 concurrent searches with asyncio.gather ===")
    t0 = time.perf_counter()
    tick_task = asyncio.create_task(ticker())      # proves the client stays responsive
    try:
        results = await asyncio.gather(
            *(one_search(stub, i + 1, kw, timeout, t0) for i, kw in enumerate(SEARCH_KEYWORDS))
        )
    finally:
        tick_task.cancel()
        try:
            await tick_task
        except asyncio.CancelledError:
            pass
    elapsed = time.perf_counter() - t0
    ok = sum(1 for _, _, n in results if n >= 0)
    print(f"\n  {ok}/{len(results)} searches answered in {elapsed:.2f}s total")
    return elapsed


async def main_async(port, timeout):
    async with grpc.aio.insecure_channel(f"localhost:{port}") as channel:
        stub = rental_pb2_grpc.RentalServiceStub(channel)
        await demo_sequential(stub, timeout)
        await demo_concurrent(stub, timeout)


def main():
    parser = argparse.ArgumentParser(description="Textbook Rental Hub - async gRPC client")
    parser.add_argument("--port", type=int, default=50052)
    parser.add_argument("--timeout", type=float, default=5.0, help="deadline per call (seconds)")
    args = parser.parse_args()
    try:
        asyncio.run(main_async(args.port, args.timeout))
    except ServerUnavailable:
        print("\nAborting demo: server is down.")
        sys.exit(1)


if __name__ == "__main__":
    main()
