"""
sample_data.py
Creates a BookCatalog filled with example textbooks.
The demo, the tests and (later) the gRPC servers can all reuse this.
"""

from book_catalog import BookCatalog


def create_sample_catalog():
    catalog = BookCatalog()
    catalog.add_book("B001", "Introduction to Algorithms", 15.0, 3)
    catalog.add_book("B002", "Distributed Systems: Concepts and Design", 12.5, 2)
    catalog.add_book("B003", "Computer Networking: A Top-Down Approach", 10.0, 1)
    catalog.add_book("B004", "Database System Concepts", 11.0, 0)   # out of stock on purpose
    catalog.add_book("B005", "Operating System Concepts", 9.5, 4)
    return catalog
