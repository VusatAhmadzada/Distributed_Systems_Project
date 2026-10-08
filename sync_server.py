"""
sync_server.py
Synchronous gRPC server for the Textbook Rental Hub.

Each handler: read the request -> call the Person 1 method -> copy the result
into a response message. No business logic lives here.

Run:  python sync_server.py [--port 50051] [--delay 0] [--workers 10]
"""

import argparse
import time
from concurrent import futures

import grpc

import rental_pb2
import rental_pb2_grpc
from rental_manager import RentalManager
from sample_data import create_sample_catalog


def book_to_pb(book):
    """Person 1 Book -> protobuf Book."""
    return rental_pb2.Book(
        book_id=book.book_id, title=book.title, price=book.price, stock=book.stock
    )


def rental_to_pb(rental):
    """Person 1 Rental -> protobuf Rental."""
    return rental_pb2.Rental(
        rental_id=rental.rental_id,
        student_id=rental.student_id,
        book_id=rental.book_id,
        price=rental.price,
    )


def result_to_pb(result):
    """Person 1 RentalResult -> protobuf RentalResponse."""
    return rental_pb2.RentalResponse(
        success=result.success,
        message=result.message,
        rental_id=result.rental_id,
        remaining_stock=result.remaining_stock,
    )


class RentalServicer(rental_pb2_grpc.RentalServiceServicer):
    def __init__(self, delay=0.0):
        # Created ONCE, so stock and rentals persist between RPC calls.
        self.catalog = create_sample_catalog()
        self.manager = RentalManager(self.catalog)
        self.delay = delay   # artificial latency (seconds) for timing experiments

    def _simulate_delay(self):
        if self.delay > 0:
            time.sleep(self.delay)   # blocks this worker thread only

    def RentBook(self, request, context):
        self._simulate_delay()
        result = self.manager.rent_book(request.student_id, request.book_id)
        return result_to_pb(result)

    def SearchBooks(self, request, context):
        self._simulate_delay()
        if request.keyword:
            books = self.catalog.search_books(request.keyword)
        else:
            books = self.catalog.list_books()
        return rental_pb2.SearchResponse(books=[book_to_pb(b) for b in books])

    def CheckStock(self, request, context):
        self._simulate_delay()
        stock = self.catalog.check_stock(request.book_id)
        return rental_pb2.StockResponse(
            book_id=request.book_id, stock=stock, found=(stock >= 0)
        )

    def ListActiveRentals(self, request, context):
        self._simulate_delay()
        rentals = self.manager.get_active_rentals(request.student_id or None)
        return rental_pb2.RentalsResponse(rentals=[rental_to_pb(r) for r in rentals])

    def ReturnBook(self, request, context):
        self._simulate_delay()
        result = self.manager.return_book(request.rental_id)
        return result_to_pb(result)


def build_server(port=50051, delay=0.0, max_workers=10):
    """Create (but do not start) a server. Returns (server, bound_port).
    port=0 lets the OS pick a free port (used by the tests)."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    rental_pb2_grpc.add_RentalServiceServicer_to_server(RentalServicer(delay), server)
    bound_port = server.add_insecure_port(f"localhost:{port}")
    if bound_port == 0:
        raise RuntimeError(f"Could not bind to localhost:{port}")
    return server, bound_port


def main():
    parser = argparse.ArgumentParser(description="Textbook Rental Hub - sync gRPC server")
    parser.add_argument("--port", type=int, default=50051)
    parser.add_argument("--delay", type=float, default=0.0,
                        help="seconds each handler sleeps (default 0)")
    parser.add_argument("--workers", type=int, default=10,
                        help="ThreadPoolExecutor size (default 10)")
    args = parser.parse_args()

    server, port = build_server(args.port, args.delay, args.workers)
    server.start()
    print(f"Sync gRPC server listening on localhost:{port} "
          f"(workers={args.workers}, delay={args.delay}s). Ctrl+C to stop.")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.stop(grace=1)


if __name__ == "__main__":
    main()
