"""
test_async_grpc.py
End-to-end tests for the asynchronous gRPC server. A real grpc.aio server is
started on a free local port (port 0) for every test and called over the network
with the generated async stub.
Run:  python -m unittest -v test_async_grpc
"""

import asyncio
import os
import time
import unittest

os.environ.setdefault("GRPC_VERBOSITY", "ERROR")   # hide harmless transport logs

import grpc

import rental_pb2
import rental_pb2_grpc
from async_server import create_server

TIMEOUT = 5


class AsyncGrpcTestCase(unittest.IsolatedAsyncioTestCase):
    DELAY = 0.0

    async def asyncSetUp(self):
        
        self.server, self.port = await create_server(port=0, delay=self.DELAY)
        await self.server.start()
        self.channel = grpc.aio.insecure_channel(f"localhost:{self.port}")
        self.stub = rental_pb2_grpc.RentalServiceStub(self.channel)

    async def asyncTearDown(self):
        await self.channel.close()
        await self.server.stop(grace=None)

    async def rent(self, student, book):
        return await self.stub.RentBook(
            rental_pb2.BookRequest(student_id=student, book_id=book), timeout=TIMEOUT)

    async def stock(self, book):
        return await self.stub.CheckStock(
            rental_pb2.StockRequest(book_id=book), timeout=TIMEOUT)

    async def search(self, keyword):
        return await self.stub.SearchBooks(
            rental_pb2.SearchRequest(keyword=keyword), timeout=TIMEOUT)


class TestRentBook(AsyncGrpcTestCase):
    async def test_successful_rental_reduces_stock(self):
        r = await self.rent("S1001", "B001")
        self.assertTrue(r.success)
        self.assertEqual(r.rental_id, "R0001")
        self.assertEqual(r.remaining_stock, 2)
        self.assertEqual((await self.stock("B001")).stock, 2)

    async def test_state_persists_between_calls(self):
        self.assertEqual((await self.rent("S1001", "B001")).rental_id, "R0001")
        self.assertEqual((await self.rent("S1002", "B001")).rental_id, "R0002")

    async def test_out_of_stock_fails(self):
        r = await self.rent("S1001", "B004")
        self.assertFalse(r.success)
        self.assertIn("out of stock", r.message)
        self.assertEqual(r.rental_id, "")

    async def test_unknown_book_fails(self):
        r = await self.rent("S1001", "B999")
        self.assertFalse(r.success)
        self.assertEqual(r.remaining_stock, -1)

    async def test_empty_student_id_fails(self):
        r = await self.rent("", "B001")
        self.assertFalse(r.success)
        self.assertIn("Student ID", r.message)


class TestSearchAndStock(AsyncGrpcTestCase):
    async def test_search_is_case_insensitive(self):
        lower = await self.search("system")
        upper = await self.search("SYSTEM")
        self.assertEqual([b.book_id for b in lower.books], [b.book_id for b in upper.books])
        self.assertEqual({b.book_id for b in lower.books}, {"B002", "B004", "B005"})

    async def test_empty_keyword_lists_all_books(self):
        self.assertEqual(len((await self.search("")).books), 5)

    async def test_no_match_returns_empty_list(self):
        self.assertEqual(len((await self.search("zzz")).books), 0)

    async def test_check_stock_known_and_zero(self):
        r = await self.stock("B001")
        self.assertEqual((r.stock, r.found), (3, True))
        r = await self.stock("B004")
        self.assertEqual((r.stock, r.found), (0, True))

    async def test_check_stock_unknown_book(self):
        r = await self.stock("B999")
        self.assertEqual((r.stock, r.found), (-1, False))


class TestRentalsAndReturn(AsyncGrpcTestCase):
    async def test_list_active_rentals_all_and_per_student(self):
        await self.rent("S1001", "B001")
        await self.rent("S1002", "B002")
        everyone = await self.stub.ListActiveRentals(rental_pb2.RentalsRequest(), timeout=TIMEOUT)
        self.assertEqual(len(everyone.rentals), 2)
        mine = await self.stub.ListActiveRentals(
            rental_pb2.RentalsRequest(student_id="S1001"), timeout=TIMEOUT)
        self.assertEqual([r.book_id for r in mine.rentals], ["B001"])

    async def test_return_book_restores_stock(self):
        rid = (await self.rent("S1001", "B003")).rental_id
        self.assertEqual((await self.stock("B003")).stock, 0)
        r = await self.stub.ReturnBook(rental_pb2.ReturnRequest(rental_id=rid), timeout=TIMEOUT)
        self.assertTrue(r.success)
        self.assertEqual((await self.stock("B003")).stock, 1)

    async def test_return_unknown_rental_fails(self):
        r = await self.stub.ReturnBook(rental_pb2.ReturnRequest(rental_id="R9999"), timeout=TIMEOUT)
        self.assertFalse(r.success)


class TestConcurrency(AsyncGrpcTestCase):
    async def test_10_concurrent_searches_all_correct(self):
        keywords = ["algorithms", "systems", "database", "networking", "operating"] * 2
        responses = await asyncio.gather(*(self.search(k) for k in keywords))
        for kw, resp in zip(keywords, responses):
            self.assertGreaterEqual(len(resp.books), 1, kw)
            self.assertTrue(all(kw[:5] in b.title.lower() for b in resp.books), kw)

    async def test_20_concurrent_rentals_last_copy_has_one_winner(self):
        results = await asyncio.gather(*(self.rent(f"S{2000 + i}", "B003") for i in range(20)))
        self.assertEqual(sum(1 for r in results if r.success), 1)
        self.assertEqual((await self.stock("B003")).stock, 0)
        active = await self.stub.ListActiveRentals(rental_pb2.RentalsRequest(), timeout=TIMEOUT)
        self.assertEqual(len(active.rentals), 1)


class TestConcurrentTiming(AsyncGrpcTestCase):
    DELAY = 0.3

    async def test_gathered_searches_overlap_in_time(self):
        await self.search("warm")                      # connection set-up
        t0 = time.perf_counter()
        await asyncio.gather(*(self.search("system") for _ in range(10)))
        elapsed = time.perf_counter() - t0
        # sequential would take 10 x 0.3 = 3.0 s; concurrent takes about 0.3 s
        self.assertLess(elapsed, 1.5)


class TestClientStaysResponsive(AsyncGrpcTestCase):
    DELAY = 0.5

    async def test_background_task_keeps_running_while_requests_wait(self):
        ticks = 0

        async def count():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.05)
                ticks += 1

        task = asyncio.create_task(count())
        await asyncio.gather(*(self.search("system") for _ in range(10)))
        task.cancel()
        # about 0.5 s of waiting at 0.05 s per tick: the client was NOT frozen
        self.assertGreaterEqual(ticks, 5)


class TestDeadline(AsyncGrpcTestCase):
    DELAY = 1.0

    async def test_short_timeout_gives_deadline_exceeded(self):
        with self.assertRaises(grpc.aio.AioRpcError) as ctx:
            await self.stub.SearchBooks(rental_pb2.SearchRequest(keyword="a"), timeout=0.2)
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.DEADLINE_EXCEEDED)


if __name__ == "__main__":
    unittest.main()
