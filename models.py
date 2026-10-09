"""
models.py
Simple data objects used by BookCatalog and RentalManager.

These classes only HOLD data. They contain no business logic.
Their fields map directly onto the messages in rental.proto.
"""

from dataclasses import dataclass


@dataclass
class Book:
    """One textbook title in the catalog."""
    book_id: str     
    title: str        
    price: float      
    stock: int        


@dataclass
class Rental:
    """One active rental: which student has which book."""
    rental_id: str   
    student_id: str   
    book_id: str      
    price: float      


@dataclass
class RentalResult:
    """The answer RentalManager gives back after a rental/return request."""
    success: bool            
    message: str             
    rental_id: str = ""      
    remaining_stock: int = 0 
