"""
rental_manager.py
RentalManager = the Business Logic class.
It receives rental requests from students, asks BookCatalog about the book,
updates the stock and remembers who rented what.
It contains no gRPC or network code: it takes plain values and returns plain objects.
"""

import threading

from book_catalog import BookCatalog
from models import Rental, RentalResult


class RentalManager:
    def __init__(self, catalog: BookCatalog):
        # RentalManager USES a BookCatalog that is created outside and passed in.
        self._catalog = catalog
        # rental_id -> Rental (only active, not yet returned, rentals)
        self._active_rentals = {}
        self._next_id = 1
        # Lock: only one request at a time may check and change stock.
        # Needed because a synchronous gRPC server runs requests in parallel threads.
        self._lock = threading.Lock()

    def rent_book(self, student_id, book_id):
        """Handle a checkout request. Always returns a RentalResult."""
        if not student_id:
            return RentalResult(False, "Student ID is required")

        with self._lock:
            book = self._catalog.get_book(book_id)
            if book is None:
                return RentalResult(False, f"Book {book_id} does not exist", remaining_stock=-1)

            if not self._catalog.is_available(book_id):
                return RentalResult(False, f"'{book.title}' is out of stock", remaining_stock=0)

            self._catalog.decrease_stock(book_id)

            rental_id = f"R{self._next_id:04d}"   # R0001, R0002, ...
            self._next_id += 1
            self._active_rentals[rental_id] = Rental(rental_id, student_id, book_id, book.price)

            return RentalResult(
                True,
                f"'{book.title}' rented to {student_id}",
                rental_id=rental_id,
                remaining_stock=self._catalog.check_stock(book_id),
            )

    def return_book(self, rental_id):
        """Optional feature (not required by the homework):
        close an active rental and put the copy back into stock."""
        with self._lock:
            rental = self._active_rentals.pop(rental_id, None)
            if rental is None:
                return RentalResult(False, f"Rental {rental_id} not found")
            self._catalog.increase_stock(rental.book_id)
            return RentalResult(
                True,
                f"Rental {rental_id} returned",
                rental_id=rental_id,
                remaining_stock=self._catalog.check_stock(rental.book_id),
            )

    def get_active_rentals(self, student_id=None):
        """Return all active rentals, or only those of one student."""
        with self._lock:
            rentals = list(self._active_rentals.values())
        if student_id:
            rentals = [r for r in rentals if r.student_id == student_id]
        return rentals
