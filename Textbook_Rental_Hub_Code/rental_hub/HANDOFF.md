> **Update:** this file is the original Person 1 -> Person 2 handoff. The final gRPC contract is
> `rental.proto`; where the two differ, the .proto wins. Differences from the proposal below:
> `StockResponse` also has a `found` flag, and `SearchBooks` with an empty keyword returns all books
> (`list_books()`). See `README.md` for how to run everything and `HANDOFF_PERSON3.md` for the async part.

# Handoff to Person 2/3 — OOP layer of the Textbook Rental Hub (Person 1)

## Files you need
Copy these into the same folder as your server code:
- `models.py` — data classes `Book`, `Rental`, `RentalResult`
- `book_catalog.py` — class `BookCatalog`
- `rental_manager.py` — class `RentalManager`
- `sample_data.py` — `create_sample_catalog()` (5 example books, B001–B005; B004 has stock 0)

Standard library only, no extra packages. These files contain no gRPC, protobuf or network code.

## Create the objects ONCE, when the server starts
```python
from sample_data import create_sample_catalog
from rental_manager import RentalManager

catalog = create_sample_catalog()      # BookCatalog
manager = RentalManager(catalog)       # RentalManager, uses that same catalog
```
Keep them in your servicer (e.g. `self.catalog`, `self.manager`). If you create new objects
inside each RPC handler, stock and rentals reset on every call.

## Methods you can call

### BookCatalog
| Method | Inputs | Returns |
|---|---|---|
| `get_book(book_id)` | str | copy of `Book`, or `None` |
| `list_books()` | — | `list[Book]` (copies) |
| `search_books(keyword)` | str | `list[Book]` (copies, case-insensitive title match) |
| `check_stock(book_id)` | str | `int` (−1 = book does not exist) |
| `is_available(book_id)` | str | `bool` |

`Book` fields: `book_id: str`, `title: str`, `price: float`, `stock: int`

Do not call `decrease_stock` / `increase_stock` from the server. Go through `RentalManager`,
so every stock change is also recorded as a rental.

### RentalManager
| Method | Inputs | Returns |
|---|---|---|
| `rent_book(student_id, book_id)` | str, str | `RentalResult` |
| `get_active_rentals(student_id=None)` | str or None | `list[Rental]` |
| `return_book(rental_id)` *(optional feature)* | str | `RentalResult` |

`RentalResult` fields: `success: bool`, `message: str`, `rental_id: str` ("" on failure), `remaining_stock: int`
`Rental` fields: `rental_id: str`, `student_id: str`, `book_id: str`, `price: float`

Normal failures (unknown book, out of stock, empty student ID, unknown rental) do NOT raise
exceptions. They return `success=False` with a message.

## The request flow (what your handler does)
```
gRPC request ─► your handler ─► manager.rent_book(...) ─► BookCatalog ─► RentalResult ─► gRPC response
```
Conceptually, for Person 2 (names are examples; the .proto is your decision):
```python
def RentBook(self, request, context):
    r = self.manager.rent_book(request.student_id, request.book_id)   # plain strings in
    return rental_pb2.RentalResponse(success=r.success, message=r.message,
                                     rental_id=r.rental_id, remaining_stock=r.remaining_stock)
```

## PROPOSED interface only — Person 2 decides the final .proto
| Python method | Possible RPC | Possible messages |
|---|---|---|
| `manager.rent_book` | `RentBook` (the sync unary call the homework requires) | `BookRequest{student_id, book_id}` → `RentalResponse{success, message, rental_id, remaining_stock}` |
| `catalog.search_books` | `SearchBooks` (fits the "concurrent student search queries" in the async part) | `SearchRequest{keyword}` → `SearchResponse{repeated Book books}` |
| `catalog.check_stock` | `CheckStock` | `StockRequest{book_id}` → `StockResponse{book_id, stock}` |
| `manager.get_active_rentals` | `ListActiveRentals` | `RentalsRequest{student_id}` → `RentalsResponse{repeated Rental rentals}` |
| `manager.return_book` | `ReturnBook` (optional) | `ReturnRequest{rental_id}` → `RentalResponse` |

## Notes
- Thread safety: `rent_book`, `return_book` and `get_active_rentals` use a `threading.Lock`.
  The sync server's ThreadPoolExecutor therefore cannot rent the last copy twice
  (checked locally: 50 parallel threads asking for B003 → exactly 1 success).
- Async (Person 3): the methods are normal, fast functions with no `await` inside.
  Inside an `async def` handler, call them directly: `r = self.manager.rent_book(...)` (no `await`).
- Proto3 has no `None`. For "book not found" you can return `stock = -1` (as `check_stock` does),
  a `found=false` field, or the gRPC status `NOT_FOUND`. Your choice.
- After any change to these files, run `python -m unittest -v` (13 tests).
