"""
sync_client.py
Demonstrates every RPC of the Textbook Rental Hub with error handling.

Run (server must be running):  python sync_client.py [--port 50051] [--timeout 2]
"""

import argparse
import sys

import grpc

import rental_pb2
import rental_pb2_grpc


class ServerUnavailable(Exception):
    """Raised by call() when the server cannot be reached."""


def call(label, rpc, request, timeout):
    """Run one unary RPC with a deadline. Returns the response, or None on a
    handled error. Raises ServerUnavailable when the server is down."""
    try:
        return rpc(request, timeout=timeout)
    except grpc.RpcError as err:
        code = err.code()
        if code == grpc.StatusCode.UNAVAILABLE:
            print(f"  [UNAVAILABLE] {label}: cannot reach the server. "
                  f"Is sync_server.py running on the right port?")
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


def run_demo(stub, timeout):
    print("1) Successful rental (S1001 rents B001):")
    r = call("RentBook", stub.RentBook,
             rental_pb2.BookRequest(student_id="S1001", book_id="B001"), timeout)
    if r:
        show_rental(r)
    first_rental_id = r.rental_id if r else ""

    print("\n2) Out-of-stock book (B004):")
    r = call("RentBook", stub.RentBook,
             rental_pb2.BookRequest(student_id="S1001", book_id="B004"), timeout)
    if r:
        show_rental(r)

    print("\n3) Unknown book (B999):")
    r = call("RentBook", stub.RentBook,
             rental_pb2.BookRequest(student_id="S1001", book_id="B999"), timeout)
    if r:
        show_rental(r)

    print("\n4) Search for 'system':")
    r = call("SearchBooks", stub.SearchBooks, rental_pb2.SearchRequest(keyword="system"), timeout)
    if r:
        for b in r.books:
            print(f"  {b.book_id} | {b.title:<42} | {b.price:5.2f} AZN | stock: {b.stock}")

    print("\n5) Stock check:")
    for book_id in ("B001", "B004", "B999"):
        r = call("CheckStock", stub.CheckStock, rental_pb2.StockRequest(book_id=book_id), timeout)
        if r:
            note = "" if r.found else "  (book does not exist)"
            print(f"  {r.book_id}: stock = {r.stock}{note}")

    print("\n6) Active rentals (all students):")
    r = call("ListActiveRentals", stub.ListActiveRentals, rental_pb2.RentalsRequest(), timeout)
    if r:
        for x in r.rentals:
            print(f"  {x.rental_id}: student {x.student_id} has {x.book_id} ({x.price:.2f} AZN)")

    print("\n7) Return the book (optional RPC):")
    if first_rental_id:
        r = call("ReturnBook", stub.ReturnBook,
                 rental_pb2.ReturnRequest(rental_id=first_rental_id), timeout)
        if r:
            show_rental(r)
    r = call("ReturnBook", stub.ReturnBook, rental_pb2.ReturnRequest(rental_id="R9999"), timeout)
    if r:
        show_rental(r)


def main():
    parser = argparse.ArgumentParser(description="Textbook Rental Hub - sync gRPC client")
    parser.add_argument("--port", type=int, default=50051)
    parser.add_argument("--timeout", type=float, default=2.0, help="deadline per call (seconds)")
    args = parser.parse_args()

    with grpc.insecure_channel(f"localhost:{args.port}") as channel:
        stub = rental_pb2_grpc.RentalServiceStub(channel)
        try:
            run_demo(stub, args.timeout)
        except ServerUnavailable:
            print("\nAborting demo: server is down.")
            sys.exit(1)


if __name__ == "__main__":
    main()
