from datetime import datetime
from flask import url_for

from . import db

# Save ourselves some typing...
Col = db.Column
String = db.String
Integer = db.Integer
Date = db.Date
DateTime = db.DateTime
Numeric = db.Numeric
Boolean = db.Boolean
ForeignKey = db.ForeignKey
Table = db.Table
relationship = db.relationship
backref = db.backref
Model = db.Model

book_category = Table(
    'book_category',
    Col('book_id', Integer, ForeignKey('book.id')),
    Col('category_id', Integer, ForeignKey('category.id'))
)

book_favorite = Table(
    'book_favorite',
    Col('book_id', Integer, ForeignKey('book.id')),
    Col('user_id', Integer, ForeignKey('user.id'))
)


class BookBorrower(Model):
    """Model that represents a user borrowing a book from the library.
    `due_date` is set for 30 days from the date of borrowing. As long as
    `returned` is False the book will be unavailable for someone else to
    borrow.
    """
    __tablename__ = 'book_borrower'
    id = Col(Integer, primary_key=True)
    user_id = Col(Integer, ForeignKey('user.id'))
    book_id = Col(Integer, ForeignKey('book.id'))
    due_date = Col(Date)
    returned = Col(Boolean, default=False)
    borrower = relationship('User')


class BookRating(Model):
    """Model that represents a user rating a book, including an optional
    text review.
    """
    __tablename__ = 'book_rating'
    user_id = Col(Integer, ForeignKey('user.id'), primary_key=True)
    book_id = Col(Integer, ForeignKey('book.id'), primary_key=True)
    rating = Col(Numeric)
    review = Col(String)
    rater = relationship('User')


class User(Model):
    """Model that represents a user. Nothing fancy."""
    __tablename__ = 'user'
    name = Col(String(250))
    id = Col(Integer, primary_key=True)
    email = Col(String(250), nullable=False, unique=True)
    picture = Col(String(250))
    date_created = Col(DateTime, default=datetime.now)

    __mapper_args__ = {
        'order_by': email  # order lists of users by email by default
    }

    def __unicode__(self):
        """Return the user's name if available, otherwise the email
        address.
        """
        if (self.name):
            return self.name
        else:
            return self.email


class Book(Model):
    """Model that represents a book. Pretty much what you would expect.
    `year_published`, `synopsis` and `picture` can be defined by the
    user or be derived from the Google Books API if available.
    """
    __tablename__ = 'book'
    title = Col(String(250), nullable=False)
    id = Col(Integer, primary_key=True)
    date_added = Col(DateTime, default=datetime.now)
    author = Col(String(250), nullable=False)
    picture = Col(String(250))
    year_published = Col(Integer)
    synopsis = Col(String)
    lender_id = Col(Integer, ForeignKey('user.id'), nullable=False)
    lender = relationship('User')
    category = relationship(
        'Category', secondary=book_category, backref=backref('books'))
    borrower = relationship('BookBorrower')
    rating = relationship('BookRating')
    favorite = relationship(
        'User', secondary=book_favorite, backref=backref('favorite_books'))

    __mapper_args__ = {
        'order_by': title  # order lists of books by title by default
    }

    def __unicode__(self):
        # return book's title when calling the object
        return self.title

    def is_available(self):
        """Check to see if book is available (i.e.: is there a related
        BookBorrower object where `returned` is False). Returns a list
        containing:
            o If the book is available (boolean)
            o When it's due back if False (date as string)
            o Who currently has it out (dict of name and email)
        """
        borrowers = self.borrower
        available = [True, None, None]
        for b in borrowers:
            # iterate through the list of borrowers and look for
            # `returned` = False
            if not b.returned:
                available = [
                    False,
                    b.due_date.strftime('%m/%d/%Y'),
                    {
                        'name': b.borrower.name,
                        'email': b.borrower.email
                    }
                ]
        return available

    def calc_rating(self):
        """Calculate average rating for the book based on individual
        ratings.
        """
        ratings = self.rating
        rateVal = 0.0
        for r in ratings:
            rateVal = rateVal + float(r.rating)

        if (rateVal == 0 or len(ratings) == 0):
            return 0
        else:
            return round((rateVal / len(ratings)), 2)

    @property
    def serialize(self):
        """Return a dict of the Book object, for use with JSON, XML,
        Atom or RSS serializer.
        """
        availability = self.is_available()

        if ('http' in self.picture):
            # if picture is an external file, probably from the Google
            # Books API, return the full URL
            pic = self.picture
        else:
            # otherwise render the appropriate `media` URL
            pic = url_for('home.media', filename=self.picture, _external=True)

        return {
            'title': self.title,
            'author': self.author,
            'date_added': self.date_added,
            'id': self.id,
            'synopsis': self.synopsis,
            'year_published': self.year_published,
            'picture': pic,
            'lender': self.lender.email,
            'is_available': availability[0],
            'due_date': availability[1],
            'borrower': availability[2]
        }


class Category(Model):
    """Model representinga Category, or Genre, of a book. Books can be
    associated with more than one Category. Includes a column_property
    for the number of books in a particular Category
    """
    __tablename__ = 'category'
    id = Col(Integer, primary_key=True)
    name = Col(String(50), nullable=False)
    book_count = db.column_property(
        db.select(
            [db.func.count(book_category.c.book_id)]
        ).where(
            book_category.c.category_id == id).correlate_except(book_category))

    __mapper_args__ = {
        'order_by': name  # order lists of categories by name by default
    }

    def __unicode__(self):
        # return the category name when calling the object
        return self.name
