"""
async_server.py
Asynchronous gRPC server for the Textbook Rental Hub (Person 3).

Same service contract (rental.proto) and the same OOP classes as sync_server.py.
The only difference is HOW requests are scheduled: grpc.aio runs every handler as
a coroutine on ONE asyncio event loop instead of one thread per request.

  - Handlers are `async def`.
  - The artificial --delay uses `await asyncio.sleep(...)`. It hands control back
    to the event loop, so other requests run while this one "waits".
    time.sleep() would freeze the whole loop and remove all concurrency.
  - The OOP methods are fast and contain no I/O, so they are called directly
    (no await). The lock inside RentalManager is never held across an await,
    so it cannot cause a deadlock.

Run:  python async_server.py [--port 50052] [--delay 0]
"""

import argparse
import asyncio

import grpc

import rental_pb2
import rental_pb2_grpc
from rental_manager import RentalManager
from sample_data import create_sample_catalog
from sync_server import book_to_pb, rental_to_pb, result_to_pb   # reuse converters


class AsyncRentalServicer(rental_pb2_grpc.RentalServiceServicer):
    def __init__(self, delay=0.0):
        # Created ONCE, so stock and rentals persist between RPC calls.
        self.catalog = create_sample_catalog()
        self.manager = RentalManager(self.catalog)
        self.delay = delay   # artificial latency (seconds) for timing experiments

    async def _simulate_delay(self):
        if self.delay > 0:
            await asyncio.sleep(self.delay)   # yields to the event loop

    async def RentBook(self, request, context):
        await self._simulate_delay()
        result = self.manager.rent_book(request.student_id, request.book_id)
        return result_to_pb(result)

    async def SearchBooks(self, request, context):
        await self._simulate_delay()
        if request.keyword:
            books = self.catalog.search_books(request.keyword)
        else:
            books = self.catalog.list_books()
        return rental_pb2.SearchResponse(books=[book_to_pb(b) for b in books])

    async def CheckStock(self, request, context):
        await self._simulate_delay()
        stock = self.catalog.check_stock(request.book_id)
        return rental_pb2.StockResponse(
            book_id=request.book_id, stock=stock, found=(stock >= 0)
        )

    async def ListActiveRentals(self, request, context):
        await self._simulate_delay()
        rentals = self.manager.get_active_rentals(request.student_id or None)
        return rental_pb2.RentalsResponse(rentals=[rental_to_pb(r) for r in rentals])

    async def ReturnBook(self, request, context):
        await self._simulate_delay()
        result = self.manager.return_book(request.rental_id)
        return result_to_pb(result)


async def create_server(port=50052, delay=0.0):
    """Create (but do not start) an async server. Returns (server, bound_port).
    port=0 lets the OS pick a free port (used by the tests).
    Must be awaited from inside a running event loop."""
    server = grpc.aio.server()
    rental_pb2_grpc.add_RentalServiceServicer_to_server(AsyncRentalServicer(delay), server)
    bound_port = server.add_insecure_port(f"localhost:{port}")
    if bound_port == 0:
        raise RuntimeError(f"Could not bind to localhost:{port}")
    return server, bound_port


async def serve(port, delay):
    server, bound = await create_server(port, delay)
    await server.start()
    print(f"Async gRPC server listening on localhost:{bound} "
          f"(delay={delay}s, one event loop). Ctrl+C to stop.")
    try:
        await server.wait_for_termination()
    except asyncio.CancelledError:
        pass
    finally:
        await server.stop(grace=1)


def main():
    parser = argparse.ArgumentParser(description="Textbook Rental Hub - async gRPC server")
    parser.add_argument("--port", type=int, default=50052)
    parser.add_argument("--delay", type=float, default=0.0,
                        help="seconds each handler awaits (default 0)")
    args = parser.parse_args()
    try:
        asyncio.run(serve(args.port, args.delay))
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
