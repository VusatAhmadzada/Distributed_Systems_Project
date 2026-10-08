"""
demo.py
Local demonstration of BookCatalog + RentalManager WITHOUT gRPC.
Run:  python demo.py
"""

from rental_manager import RentalManager
from sample_data import create_sample_catalog


def print_books(books):
    for b in books:
        print(f"  {b.book_id} | {b.title:<42} | {b.price:5.2f} AZN | stock: {b.stock}")


def print_result(result):
    status = "SUCCESS" if result.success else "FAILED "
    extra = f" (rental {result.rental_id})" if result.rental_id else ""
    print(f"  [{status}] {result.message}{extra}")


def main():
    catalog = create_sample_catalog()
    manager = RentalManager(catalog)

    print("1) All books in the catalog:")
    print_books(catalog.list_books())

    print("\n2) Search for 'system':")
    print_books(catalog.search_books("system"))

    print("\n3) Check stock:")
    print(f"  B001 stock = {catalog.check_stock('B001')}")
    print(f"  B999 stock = {catalog.check_stock('B999')}  (-1 means the book does not exist)")

    print("\n4) Successful rentals:")
    print_result(manager.rent_book("S1001", "B001"))
    print_result(manager.rent_book("S1002", "B003"))
    print(f"  B001 stock is now {catalog.check_stock('B001')} (was 3)")
    print(f"  B003 stock is now {catalog.check_stock('B003')} (was 1)")

    print("\n5) Failed rentals:")
    print_result(manager.rent_book("S1003", "B003"))  # last copy already taken
    print_result(manager.rent_book("S1003", "B004"))  # stock was 0 from the start
    print_result(manager.rent_book("S1003", "B999"))  # does not exist

    print("\n6) Active rentals:")
    for r in manager.get_active_rentals():
        print(f"  {r.rental_id}: student {r.student_id} has {r.book_id} ({r.price:.2f} AZN)")

    print("\n7) Return a book:")
    print_result(manager.return_book("R0002"))
    print(f"  B003 stock is now {catalog.check_stock('B003')}")
    print(f"  Active rentals left: {len(manager.get_active_rentals())}")


if __name__ == "__main__":
    main()
