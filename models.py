"""
models.py
Simple data objects used by BookCatalog and RentalManager.

These classes only HOLD data. They contain no business logic.
Later, Person 2 can copy their fields almost 1-to-1 into .proto messages.
"""

from dataclasses import dataclass


@dataclass
class Book:
    """One textbook title in the catalog."""
    book_id: str      # unique ID, e.g. "B001"
    title: str        # e.g. "Introduction to Algorithms"
    price: float      # rental price in AZN
    stock: int        # how many copies are available right now


@dataclass
class Rental:
    """One active rental: which student has which book."""
    rental_id: str    # unique ID, e.g. "R0001"
    student_id: str   # e.g. "S1001"
    book_id: str      # the rented book
    price: float      # price at the moment of renting


@dataclass
class RentalResult:
    """The answer RentalManager gives back after a rental/return request."""
    success: bool            # True = it worked, False = it was rejected
    message: str             # human-readable explanation
    rental_id: str = ""      # filled only when a rental succeeds
    remaining_stock: int = 0 # stock of that book after the operation
