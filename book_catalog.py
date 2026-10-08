"""
book_catalog.py
BookCatalog = the Inventory class.
It stores books and knows their titles, prices and stock.
It does NOT know anything about students or rentals.
"""

from dataclasses import replace

from models import Book


class BookCatalog:
    def __init__(self):
        # Private dictionary: book_id -> Book
        # The leading underscore means "internal, use the methods instead".
        self._books = {}

    # ---------- adding books ----------
    def add_book(self, book_id, title, price, stock):
        """Add a new book.
        Raises ValueError for a duplicate ID or a negative price/stock."""
        if book_id in self._books:
            raise ValueError(f"Book ID {book_id} already exists")
        if price < 0 or stock < 0:
            raise ValueError("Price and stock cannot be negative")
        self._books[book_id] = Book(book_id, title, float(price), int(stock))

    # ---------- reading / searching ----------
    # These methods return COPIES of the books (replace(b) makes a copy).
    # Outside code can read a copy, but changing it does not change the catalog.
    # Stock can only change through decrease_stock / increase_stock.

    def get_book(self, book_id):
        """Return a copy of the book with this ID, or None if it does not exist."""
        book = self._books.get(book_id)
        return replace(book) if book else None

    def list_books(self):
        """Return copies of all books."""
        return [replace(b) for b in self._books.values()]

    def search_books(self, keyword):
        """Return copies of books whose title contains the keyword (case-insensitive)."""
        keyword = keyword.lower()
        return [replace(b) for b in self._books.values() if keyword in b.title.lower()]

    def check_stock(self, book_id):
        """Return the number of available copies, or -1 if the book does not exist."""
        book = self._books.get(book_id)
        return book.stock if book else -1

    def is_available(self, book_id):
        """True if the book exists and at least one copy is in stock."""
        return self.check_stock(book_id) > 0

    # ---------- changing stock ----------
    def decrease_stock(self, book_id, quantity=1):
        """Reduce stock after a successful rental. Returns True/False."""
        book = self._books.get(book_id)
        if book is None or book.stock < quantity:
            return False
        book.stock -= quantity
        return True

    def increase_stock(self, book_id, quantity=1):
        """Increase stock when a book is returned. Returns True/False."""
        book = self._books.get(book_id)
        if book is None:
            return False
        book.stock += quantity
        return True
