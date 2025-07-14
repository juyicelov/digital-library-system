from abc import ABC, abstractmethod
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime

# ORM Setup
Base = declarative_base()

class Book(Base):
    __tablename__ = 'books'
    id = Column(Integer, primary_key=True)
    title = Column(String)
    author = Column(String)
    available = Column(Boolean, default=True)

class UserModel(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    role = Column(String)

class LoanHistory(Base):
    __tablename__ = 'loan_history'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    book_id = Column(Integer, ForeignKey('books.id'))
    loan_date = Column(DateTime, default=datetime.utcnow)
    return_date = Column(DateTime, nullable=True)
    user = relationship("UserModel")
    book = relationship("Book")

engine = create_engine('sqlite:///library.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# Collection (Cache) for Book Search
class BookCache:
    def __init__(self):
        self.books = []

    def load_from_db(self, session):
        self.books = session.query(Book).all()

    def search(self, keyword):
        keyword = keyword.lower()
        return [
            book for book in self.books
            if keyword in book.title.lower() or keyword in book.author.lower()
        ]

# Abstract User
class User(ABC):
    @abstractmethod
    def get_role(self) -> str:
        pass

    @abstractmethod
    def can_borrow(self) -> bool:
        pass

class Admin(User):
    def get_role(self) -> str:
        return "Admin"

    def can_borrow(self) -> bool:
        return False

    def add_book(self, session, title, author):
        # Simpan ke cache sebelum ke DB
        existing = session.query(Book).filter_by(title=title, author=author).first()
        if existing:
            print("Buku sudah ada di database.")
            return
        book = Book(title=title, author=author, available=True)
        session.add(book)
        session.commit()
        print("Buku berhasil ditambahkan.")

    def remove_book(self, session, book_id):
        book = session.query(Book).filter_by(id=book_id).first()
        if book:
            if not book.available:
                print("Buku sedang dipinjam, tidak bisa dihapus.")
                return
            session.delete(book)
            session.commit()
            print("Buku berhasil dihapus.")
        else:
            print("Buku tidak ditemukan.")

class Member(User):
    def __init__(self, user_id):
        self.user_id = user_id

    def get_role(self) -> str:
        return "Member"

    def can_borrow(self) -> bool:
        session = Session()
        count = session.query(LoanHistory).filter_by(user_id=self.user_id, return_date=None).count()
        session.close()
        return count < 3

    def borrow_book(self, session, book_id):
        if not self.can_borrow():
            print("Anda sudah meminjam maksimal 3 buku.")
            return
        book = session.query(Book).filter_by(id=book_id).first()
        if not book or not book.available:
            print("Buku tidak tersedia untuk dipinjam.")
            return
        loan = LoanHistory(user_id=self.user_id, book_id=book_id, loan_date=datetime.utcnow())
        book.available = False
        session.add(loan)
        session.commit()
        print("Buku berhasil dipinjam.")

    def return_book(self, session, book_id):
        loan = session.query(LoanHistory).filter_by(user_id=self.user_id, book_id=book_id, return_date=None).first()
        if not loan:
            print("Tidak ada peminjaman aktif untuk buku ini.")
            return
        loan.return_date = datetime.utcnow()
        book = session.query(Book).filter_by(id=book_id).first()
        if book:
            book.available = True
        session.commit()
        print("Buku berhasil dikembalikan.")

def get_or_create_user(session, name, role):
    user = session.query(UserModel).filter_by(name=name).first()
    if not user:
        user = UserModel(name=name, role=role)
        session.add(user)
        session.commit()
    return user

if __name__ == "__main__":
    session = Session()
    print("=== Sistem Perpustakaan Dinamis ===")
    print("Login sebagai:")
    print("1. Admin")
    print("2. Member")
    while True:
        pilihan = input("Pilih (1/2): ").strip()
        if pilihan == "1":
            nama = input("Nama admin: ").strip()
            user_db = get_or_create_user(session, nama, "Admin")
            user = Admin()
            break
        elif pilihan == "2":
            nama = input("Nama member: ").strip()
            user_db = get_or_create_user(session, nama, "Member")
            user = Member(user_id=user_db.id)
            break
        else:
            print("Pilihan tidak valid. Silakan pilih kembali.")

    while True:
        print("\nMenu:")
        if user.get_role() == "Admin":
            print("1. Tambah Buku")
            print("2. Hapus Buku")
            print("3. Cari Buku")
            print("0. Keluar")
            menu = input("Pilih menu: ").strip()
            if menu == "1":
                judul = input("Judul buku: ")
                penulis = input("Penulis: ")
                user.add_book(session, judul, penulis)
            elif menu == "2":
                while True:
                    book_id_input = input("ID buku yang akan dihapus: ")
                    if book_id_input.isdigit():
                        book_id = int(book_id_input)
                        user.remove_book(session, book_id)
                        break
                    else:
                        print("ID harus berupa angka. Silakan coba lagi.")
            elif menu == "3":
                keyword = input("Kata kunci: ")
                cache = BookCache()
                cache.load_from_db(session)
                results = cache.search(keyword)
                if results:
                    for book in results:
                        print(f"{book.id}. {book.title} by {book.author} (Available: {book.available})")
                else:
                    print("Buku tidak ditemukan.")
            elif menu == "0":
                break
            else:
                print("Menu tidak valid. Silakan pilih kembali.")
        else:
            print("1. Pinjam Buku")
            print("2. Kembalikan Buku")
            print("3. Cari Buku")
            print("0. Keluar")
            menu = input("Pilih menu: ").strip()
            if menu == "1":
                while True:
                    book_id_input = input("ID buku yang akan dipinjam: ")
                    if book_id_input.isdigit():
                        book_id = int(book_id_input)
                        user.borrow_book(session, book_id)
                        break
                    else:
                        print("ID harus berupa angka. Silakan coba lagi.")
            elif menu == "2":
                while True:
                    book_id_input = input("ID buku yang akan dikembalikan: ")
                    if book_id_input.isdigit():
                        book_id = int(book_id_input)
                        user.return_book(session, book_id)
                        break
                    else:
                        print("ID harus berupa angka. Silakan coba lagi.")
            elif menu == "3":
                keyword = input("Kata kunci: ")
                cache = BookCache()
                cache.load_from_db(session)
                results = cache.search(keyword)
                if results:
                    for book in results:
                        print(f"{book.id}. {book.title} by {book.author} (Available: {book.available})")
                else:
                    print("Buku tidak ditemukan.")
            elif menu == "0":
                break
            else:
                print("Menu tidak valid. Silakan pilih kembali.")

    session.close()
    print("Terima kasih telah menggunakan sistem perpustakaan.")
