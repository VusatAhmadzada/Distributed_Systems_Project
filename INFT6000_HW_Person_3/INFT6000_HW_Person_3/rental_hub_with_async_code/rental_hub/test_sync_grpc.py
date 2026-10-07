"""
test_sync_grpc.py
End-to-end tests: a real gRPC server is started on a free local port and every
RPC is called over the network with the generated client stub.
Run:  python -m unittest -v test_sync_grpc
"""

import os
import unittest
from concurrent import futures

os.environ.setdefault("GRPC_VERBOSITY", "ERROR")   # hide harmless transport logs

import grpc

import rental_pb2
import rental_pb2_grpc
from sync_server import build_server

TIMEOUT = 5


class GrpcTestCase(unittest.TestCase):
    DELAY = 0.0

    def setUp(self):
        # Fresh server (and fresh data) for every test; port 0 = any free port.
        self.server, self.port = build_server(port=0, delay=self.DELAY)
        self.server.start()
        self.channel = grpc.insecure_channel(f"localhost:{self.port}")
        self.stub = rental_pb2_grpc.RentalServiceStub(self.channel)

    def tearDown(self):
        self.channel.close()
        self.server.stop(grace=None)

    def rent(self, student, book):
        return self.stub.RentBook(
            rental_pb2.BookRequest(student_id=student, book_id=book), timeout=TIMEOUT)

    def stock(self, book):
        return self.stub.CheckStock(
            rental_pb2.StockRequest(book_id=book), timeout=TIMEOUT)


class TestRentBook(GrpcTestCase):
    def test_successful_rental_reduces_stock(self):
        r = self.rent("S1001", "B001")
        self.assertTrue(r.success)
        self.assertEqual(r.rental_id, "R0001")
        self.assertEqual(r.remaining_stock, 2)
        self.assertEqual(self.stock("B001").stock, 2)

    def test_state_persists_between_calls(self):
        self.assertEqual(self.rent("S1001", "B001").rental_id, "R0001")
        self.assertEqual(self.rent("S1002", "B001").rental_id, "R0002")

    def test_out_of_stock_fails(self):
        r = self.rent("S1001", "B004")
        self.assertFalse(r.success)
        self.assertIn("out of stock", r.message)
        self.assertEqual(r.rental_id, "")
        self.assertEqual(self.stock("B004").stock, 0)

    def test_missing_book_fails(self):
        r = self.rent("S1001", "B999")
        self.assertFalse(r.success)
        self.assertEqual(r.remaining_stock, -1)
        rentals = self.stub.ListActiveRentals(rental_pb2.RentalsRequest(), timeout=TIMEOUT)
        self.assertEqual(len(rentals.rentals), 0)

    def test_empty_student_id_fails(self):
        self.assertFalse(self.rent("", "B001").success)

    def test_last_copy_cannot_be_rented_twice(self):
        self.assertTrue(self.rent("S1001", "B003").success)
        self.assertFalse(self.rent("S1002", "B003").success)

    def test_parallel_clients_only_one_gets_last_copy(self):
        with futures.ThreadPoolExecutor(max_workers=20) as pool:
            results = list(pool.map(lambda i: self.rent(f"S{i}", "B003"), range(20)))
        self.assertEqual(sum(r.success for r in results), 1)
        self.assertEqual(self.stock("B003").stock, 0)


class TestSearchAndStock(GrpcTestCase):
    def search(self, keyword):
        return self.stub.SearchBooks(
            rental_pb2.SearchRequest(keyword=keyword), timeout=TIMEOUT)

    def test_search_is_case_insensitive(self):
        ids = [b.book_id for b in self.search("SYSTEM").books]
        self.assertEqual(ids, ["B002", "B004", "B005"])

    def test_search_returns_all_book_fields(self):
        book = self.search("algorithms").books[0]
        self.assertEqual(book.book_id, "B001")
        self.assertEqual(book.title, "Introduction to Algorithms")
        self.assertEqual(book.price, 15.0)
        self.assertEqual(book.stock, 3)

    def test_search_no_match_is_empty(self):
        self.assertEqual(len(self.search("zzz").books), 0)

    def test_empty_keyword_lists_all_books(self):
        self.assertEqual(len(self.search("").books), 5)

    def test_check_stock(self):
        r = self.stock("B001")
        self.assertEqual((r.stock, r.found), (3, True))
        r = self.stock("B004")
        self.assertEqual((r.stock, r.found), (0, True))

    def test_check_stock_unknown_book(self):
        r = self.stock("B999")
        self.assertEqual((r.stock, r.found), (-1, False))


class TestRentalsAndReturn(GrpcTestCase):
    def active(self, student=""):
        return self.stub.ListActiveRentals(
            rental_pb2.RentalsRequest(student_id=student), timeout=TIMEOUT).rentals

    def test_active_rentals_are_stored(self):
        self.rent("S1001", "B001")
        self.rent("S1002", "B002")
        self.rent("S1001", "B005")
        self.assertEqual(len(self.active()), 3)
        self.assertEqual([r.book_id for r in self.active("S1001")], ["B001", "B005"])
        self.assertEqual(self.active("S9999"), [])

    def test_rental_fields(self):
        self.rent("S1001", "B002")
        r = self.active()[0]
        self.assertEqual((r.rental_id, r.student_id, r.book_id, r.price),
                         ("R0001", "S1001", "B002", 12.5))

    def test_return_book_restores_stock(self):
        rid = self.rent("S1001", "B003").rental_id
        self.assertEqual(self.stock("B003").stock, 0)
        ret = self.stub.ReturnBook(rental_pb2.ReturnRequest(rental_id=rid), timeout=TIMEOUT)
        self.assertTrue(ret.success)
        self.assertEqual(self.stock("B003").stock, 1)
        again = self.stub.ReturnBook(rental_pb2.ReturnRequest(rental_id=rid), timeout=TIMEOUT)
        self.assertFalse(again.success)   # cannot return twice


class TestErrorHandling(unittest.TestCase):
    def test_server_down_gives_unavailable(self):
        server, port = build_server(port=0)
        server.start()
        server.stop(grace=None).wait()         # port is now closed
        with grpc.insecure_channel(f"localhost:{port}") as ch:
            stub = rental_pb2_grpc.RentalServiceStub(ch)
            with self.assertRaises(grpc.RpcError) as cm:
                stub.CheckStock(rental_pb2.StockRequest(book_id="B001"), timeout=2)
        # a closed port normally gives UNAVAILABLE, but on some systems the
        # connection attempt times out first
        self.assertIn(cm.exception.code(),
                      (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED))


class TestDelayAndDeadline(GrpcTestCase):
    DELAY = 0.5

    def test_deadline_exceeded_when_server_is_slow(self):
        with self.assertRaises(grpc.RpcError) as cm:
            self.stub.CheckStock(rental_pb2.StockRequest(book_id="B001"), timeout=0.1)
        self.assertEqual(cm.exception.code(), grpc.StatusCode.DEADLINE_EXCEEDED)

    def test_call_succeeds_with_generous_deadline(self):
        self.assertEqual(self.stock("B001").stock, 3)


if __name__ == "__main__":
    unittest.main()
