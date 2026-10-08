"""
test_rental_hub.py
Automatic unit tests for BookCatalog and RentalManager (no gRPC).
Run from this folder:  python -m unittest -v
"""

import unittest

from book_catalog import BookCatalog
from rental_manager import RentalManager
from sample_data import create_sample_catalog


class TestBookCatalog(unittest.TestCase):
    def setUp(self):
        # runs before EVERY test, so each test starts with fresh data
        self.catalog = create_sample_catalog()

    # 1. adding / finding books
    def test_add_and_find_book(self):
        catalog = BookCatalog()
        catalog.add_book("B100", "Computer Architecture", 8.0, 2)
        book = catalog.get_book("B100")
        self.assertEqual(book.title, "Computer Architecture")
        self.assertEqual(book.price, 8.0)
        self.assertEqual(book.stock, 2)
        self.assertIsNone(catalog.get_book("B999"))

    def test_duplicate_id_rejected(self):
        with self.assertRaises(ValueError):
            self.catalog.add_book("B001", "Copy", 1.0, 1)

    # 2. searching books
    def test_search_is_case_insensitive(self):
        ids = [b.book_id for b in self.catalog.search_books("SYSTEM")]
        self.assertEqual(ids, ["B002", "B004", "B005"])

    # 3. checking stock
    def test_check_stock(self):
        self.assertEqual(self.catalog.check_stock("B001"), 3)
        self.assertEqual(self.catalog.check_stock("B999"), -1)
        self.assertTrue(self.catalog.is_available("B001"))
        self.assertFalse(self.catalog.is_available("B004"))

    def test_decrease_stock_never_below_zero(self):
        self.assertFalse(self.catalog.decrease_stock("B004"))
        self.assertEqual(self.catalog.check_stock("B004"), 0)

    def test_returned_book_is_a_copy(self):
        book = self.catalog.get_book("B001")
        book.stock = -5                       # change the copy only
        self.assertEqual(self.catalog.check_stock("B001"), 3)


class TestRentalManager(unittest.TestCase):
    def setUp(self):
        self.catalog = create_sample_catalog()
        self.manager = RentalManager(self.catalog)

    # 4. successful rental  +  5. stock decreases
    def test_successful_rental_reduces_stock(self):
        result = self.manager.rent_book("S1001", "B001")
        self.assertTrue(result.success)
        self.assertEqual(result.rental_id, "R0001")
        self.assertEqual(result.remaining_stock, 2)
        self.assertEqual(self.catalog.check_stock("B001"), 2)

    # 6. unavailable book
    def test_out_of_stock_fails(self):
        result = self.manager.rent_book("S1001", "B004")
        self.assertFalse(result.success)
        self.assertIn("out of stock", result.message)
        self.assertEqual(self.catalog.check_stock("B004"), 0)

    def test_last_copy_cannot_be_rented_twice(self):
        self.assertTrue(self.manager.rent_book("S1001", "B003").success)
        self.assertFalse(self.manager.rent_book("S1002", "B003").success)

    # 7. nonexistent book
    def test_missing_book_fails(self):
        result = self.manager.rent_book("S1001", "B999")
        self.assertFalse(result.success)
        self.assertEqual(self.manager.get_active_rentals(), [])

    def test_empty_student_id_fails(self):
        self.assertFalse(self.manager.rent_book("", "B001").success)

    # 8. active rental storage
    def test_active_rentals_are_stored(self):
        self.manager.rent_book("S1001", "B001")
        self.manager.rent_book("S1002", "B002")
        self.manager.rent_book("S1001", "B005")
        self.assertEqual(len(self.manager.get_active_rentals()), 3)
        mine = self.manager.get_active_rentals("S1001")
        self.assertEqual([r.book_id for r in mine], ["B001", "B005"])

    # optional feature: return_book
    def test_return_book_restores_stock(self):
        rental_id = self.manager.rent_book("S1001", "B003").rental_id
        self.assertEqual(self.catalog.check_stock("B003"), 0)
        self.assertTrue(self.manager.return_book(rental_id).success)
        self.assertEqual(self.catalog.check_stock("B003"), 1)
        self.assertFalse(self.manager.return_book(rental_id).success)  # cannot return twice


if __name__ == "__main__":
    unittest.main()
