import sqlite3

conn = sqlite3.connect('library.db')
conn.executescript("""
DROP TABLE IF EXISTS loans;
DROP TABLE IF EXISTS books;
DROP TABLE IF EXISTS members;

CREATE TABLE books (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    year INTEGER,
    genre TEXT
);
CREATE TABLE members (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    joined_on TEXT
);
CREATE TABLE loans (
    id INTEGER PRIMARY KEY,
    book_id INTEGER REFERENCES books(id),
    member_id INTEGER REFERENCES members(id),
    loaned_on TEXT,
    returned_on TEXT
);
""")
conn.executemany(
    "INSERT INTO books (title, author, year, genre) VALUES (?, ?, ?, ?)",
    [
        ("Dune", "Frank Herbert", 1965, "sci-fi"),
        ("Emma", "Jane Austen", 1815, "classic"),
        ("The Hobbit", "J.R.R. Tolkien", 1937, "fantasy"),
        ("Neuromancer", "William Gibson", 1984, "sci-fi"),
    ],
)
conn.executemany(
    "INSERT INTO members (name, joined_on) VALUES (?, ?)",
    [("Asha", "2024-01-10"), ("Ravi", "2024-03-22")],
)
conn.executemany(
    "INSERT INTO loans (book_id, member_id, loaned_on, returned_on) VALUES (?, ?, ?, ?)",
    [(1, 1, "2024-05-01", "2024-05-15"), (3, 2, "2024-06-02", None)],
)
conn.commit()
conn.close()