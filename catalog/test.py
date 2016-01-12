import datetime as dt
import re
import unittest
import urllib
import urlparse
import xml.etree.ElementTree as ET

from flask.ext.testing import TestCase

from catalog import app, db
from catalog.models import Book, User, Category, BookBorrower, BookRating
from catalog.forms import SearchForm, BookForm, ReviewForm
from test_utils import (
    delete_test_file,
    get_google_client_id,
    save_google_secrets_test_files
)

from sqlalchemy.orm.exc import NoResultFound
from StringIO import StringIO


"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
 SERIALIZED OBJECT DATA
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

books_json = '''{
  "Books": [
    {
      "author": "Charles Dikkens",
      "borrower": null,
      "date_added": "Mon, 04 Jan 2016 18:46:03 GMT",
      "due_date": null,
      "id": 1,
      "is_available": true,
      "lender": "admin@catalog.com",
      "picture": "http://books.google.com/books/content?id=fHI1AQAAMAAJ&printsec=frontcover&img=1&zoom=1&source=gbs_api",
      "synopsis": "By the well-known Dutch author.",
      "title": "Rarnaby Budge",
      "year_published": 1967
    },
    {
      "author": "An Irish Gentleman",
      "borrower": null,
      "date_added": "Mon, 04 Jan 2016 18:46:03 GMT",
      "due_date": null,
      "id": 2,
      "is_available": true,
      "lender": "admin@catalog.com",
      "picture": "http://books.google.com/books/content?id=dFX1xN7q-AgC&printsec=frontcover&img=1&zoom=1&source=gbs_api",
      "synopsis": "His name eludes me at the moment.",
      "title": "101 Ways to Start a Fight",
      "year_published": 1967
    }
  ]
}'''

books_xml = '''<?xml version="1.0" encoding="utf-8"?>
<books>
    <book>
        <picture>http://books.google.com/books/content?id=dFX1xN7q-AgC&amp;printsec=frontcover&amp;img=1&amp;zoom=1&amp;source=gbs_api</picture>
        <due_date>None</due_date>
        <is_available>True</is_available>
        <borrower>None</borrower>
        <date_added>2016-01-04 18:46:03</date_added>
        <id>2</id>
        <year_published>1967</year_published>
        <title>101 Ways to Start a Fight</title>
        <author>An Irish Gentleman</author>
        <lender>admin@catalog.com</lender>
        <synopsis>His name eludes me at the moment.</synopsis>
    </book>
    <book>
        <picture>http://books.google.com/books/content?id=fHI1AQAAMAAJ&amp;printsec=frontcover&amp;img=1&amp;zoom=1&amp;source=gbs_api</picture>
        <due_date>None</due_date>
        <is_available>True</is_available>
        <borrower>None</borrower>
        <date_added>2016-01-04 18:46:03</date_added>
        <id>1</id>
        <year_published>1967</year_published>
        <title>Rarnaby Budge</title>
        <author>Charles Dikkens</author>
        <lender>admin@catalog.com</lender>
        <synopsis>By the well-known Dutch author.</synopsis>
    </book>
</books>
'''

books_atom = '''<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <title>Book List from Lending Library</title>
    <link href="http://localhost/books/API/" rel="self"/>
    <id>http://localhost/</id>
    <updated>---updated---</updated>
    <entry>
        <title>Rarnaby Budge</title>
        <link href="http://localhost/books/1/info/"/>
        <id>tag:localhost,2016-01-04:/books/1/info</id>
        <updated>2016-01-04T18:46:03Z</updated>
        <summary>By the well-known Dutch author.</summary>
        <author>
            <name>Charles Dikkens</name>
        </author>
        <yearpublished>1967</yearpublished>
        <picture>http://books.google.com/books/content?id=fHI1AQAAMAAJ&amp;printsec=frontcover&amp;img=1&amp;zoom=1&amp;source=gbs_api</picture>
        <isavailable>True</isavailable>
        <lender>
            <email>admin@catalog.com</email>
        </lender>
    </entry>
</feed>
'''

books_rss = '''<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
    <channel>
        <title>Book List from Lending Library</title>
        <description>A list of books from the Lending Library.</description>
        <link>http://localhost/books/API/</link>
        <pubDate>---updated---</pubDate>
        <item>
            <title>101 Ways to Start a Fight</title>
            <link>http://localhost/books/2/info/</link>
            <pubDate>Mon, 04 Jan 2016 18:46:03 +0000</pubDate>
            <description>His name eludes me at the moment.</description>
            <author>An Irish Gentleman</author>
            <yearpublished>1967</yearpublished>
            <picture>http://books.google.com/books/content?id=dFX1xN7q-AgC&amp;printsec=frontcover&amp;img=1&amp;zoom=1&amp;source=gbs_api</picture>
            <isavailable>True</isavailable>
            <lender>admin@catalog.com</lender>
        </item>
        <item>
            <title>Rarnaby Budge</title>
            <link>http://localhost/books/1/info/</link>
            <pubDate>Mon, 04 Jan 2016 18:46:03 +0000</pubDate>
            <description>By the well-known Dutch author.</description>
            <author>Charles Dikkens</author>
            <yearpublished>1967</yearpublished>
            <picture>http://books.google.com/books/content?id=fHI1AQAAMAAJ&amp;printsec=frontcover&amp;img=1&amp;zoom=1&amp;source=gbs_api</picture>
            <isavailable>True</isavailable>
            <lender>admin@catalog.com</lender>
        </item>
    </channel>
</rss>
'''


class CatalogTestCase(TestCase):

    def create_app(self):
        """Setup test environment, including starter objects and config
        variables. Set the testing flag to True, create an in-memory
        SQLite database, add some data to test with, etc.
        """
        app.testing = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['PRESERVE_CONTEXT_ON_EXCEPTION'] = False
        app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False
        app.config['WTF_CSRF_ENABLED'] = False
        with app.app_context():
            db.drop_all()
            db.create_all()
            self.db = db

            date_added = dt.datetime.strptime(
                'Mon, 04 Jan 2016 18:46:03 GMT', '%a, %d %b %Y %H:%M:%S GMT')
            user = User(
                name='admin',
                email='admin@catalog.com'
            )

            category = Category(name='Silly Books')
            category2 = Category(name='Serious Books')

            book_pic = 'http://books.google.com/books/content?id=fHI1AQAAMAAJ'
            book_pic += '&printsec=frontcover&img=1&zoom=1&source=gbs_api'
            book = Book(
                title='Rarnaby Budge',
                author='Charles Dikkens',
                year_published=1967,
                synopsis='By the well-known Dutch author.',
                lender=user,
                category=[category, ],
                picture=book_pic,
                date_added=date_added
            )

            book2_pic = 'http://books.google.com/books/content?id=dFX1xN7q-AgC'
            book2_pic += '&printsec=frontcover&img=1&zoom=1&source=gbs_api'
            book2 = Book(
                title='101 Ways to Start a Fight',
                author='An Irish Gentleman',
                year_published=1967,
                synopsis='His name eludes me at the moment.',
                lender=user,
                category=[category2, ],
                picture=book2_pic,
                date_added=date_added
            )

            db.session.add(user)
            db.session.add(category)
            db.session.add(category2)
            db.session.add(book)
            db.session.add(book2)
            db.session.commit()
        return app

    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
     TEST APP MODEL FUNCTIONS
    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

    def test_book_is_available(self):
        """Test the Book model's `is_available()` function. It should
        return a 3-part list with:
            o If the book is available (boolean)
            o When it's due back if False (date as string)
            o Who currently has it out (dict of name and email)
        """
        book = Book.query.filter_by(title='Rarnaby Budge').one()
        user = User.query.filter_by(email='admin@catalog.com').one()

        self.assertTrue(book.is_available)

        today = dt.datetime.today()
        due_date = today + dt.timedelta(days=30)
        due_date_str = due_date.strftime('%m/%d/%Y')

        bb = BookBorrower(
            user_id=user.id,
            book_id=book.id,
            due_date=due_date
        )
        db.session.add(bb)
        db.session.commit()

        availability = book.is_available()
        self.assertFalse(availability[0])
        self.assertEqual(availability[1], due_date_str)
        self.assertEqual(availability[2]['name'], 'admin')
        self.assertEqual(availability[2]['email'], 'admin@catalog.com')

    def test_book_calc_rating(self):
        """Test the Book model's `calc_rating()` function. It should
        return a float rounded to 2 decimal points.
        """
        book = Book.query.filter_by(title='Rarnaby Budge').one()
        user = User.query.filter_by(email='admin@catalog.com').one()
        user2 = User(
            name='Proprieter',
            email='proprieter@bookshopsketch.com'
        )

        self.assertEqual(book.calc_rating(), 0)  # no ratings for this book

        br = BookRating(
            user_id=user.id,
            book_id=book.id,
            rating=3.2,
            review='I could not put it down'
        )
        db.session.add(br)
        db.session.add(user2)
        db.session.commit()

        self.assertEqual(book.calc_rating(), 3.2)

        br2 = BookRating(
            user_id=user2.id,
            book_id=book.id,
            rating=2.1,
            review='I could not pick it up'
        )
        db.session.add(br2)
        db.session.commit()

        # make sure the math is right
        # (3.2+2.1)/2 = 5.3/2 = 2.65
        self.assertEqual(book.calc_rating(), 2.65)

    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
     TEST HOME VIEWS
    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

    def test_home_catalog_home(self):
        """Test the `home.catalogHome` view. It should just render
        the appropriate template.
        """
        response = self.client.get('/')
        self.assert_200(response)
        self.assert_template_used('index.html')

    def test_home_show_books_recent(self):
        """Test the `home.showBooks` view using the default book
        filter (Recent Books). It should return a template with
        the books queryset in date order.
        """
        books = Book.query.all()

        response = self.client.get('/books/')

        self.assert_200(response)
        self.assert_template_used('books.html')

        b_list = self.get_context_variable('books')
        b_list2 = self.get_context_variable('books2')
        f_type = self.get_context_variable('f_type')
        cats = self.get_context_variable('categories')
        this_cat = self.get_context_variable('this_category')
        header = self.get_context_variable('header')
        header2 = self.get_context_variable('header2')

        # we should have 2 books in the DB
        self.assertEqual(b_list.count(), 2)

        # `book` should be listed first before `book2`
        self.assertEqual(b_list[0], books[1])

        # no second books list (used only for My Books)
        self.assertEqual(b_list2, None)

        # no filter
        self.assertEqual(f_type, '')

        # one for each book-category combo; 2 total
        self.assertEqual(cats.count(), 2)

        # category name should match
        self.assertEqual(cats[0].name, 'Serious Books')

        # no category filter
        self.assertEqual(this_cat, None)

        # check header string
        self.assertEqual(header, 'Recently Added Books')

        # no second header (only My Books)
        self.assertEqual(header2, '')

    def test_home_show_books_category(self):
        """Test the `home.showBooks` view using the category book
        filter. It should return a template with the books queryset
        containing only the one book in the requested category.
        """
        cat = Category.query.first()
        books = Book.query.filter(Book.category.contains(cat)).all()

        response = self.client.get('/books/category/' + cat.name + '/')

        self.assert_200(response)
        self.assert_template_used('books.html')

        b_list = self.get_context_variable('books')
        b_list2 = self.get_context_variable('books2')
        f_type = self.get_context_variable('f_type')
        cats = self.get_context_variable('categories')
        this_cat = self.get_context_variable('this_category')
        header = self.get_context_variable('header')
        header2 = self.get_context_variable('header2')

        # just one book in the list
        self.assertEqual(len(b_list), 1)

        # make sure it's the right book
        self.assertEqual(b_list[0], books[0])

        # no second book list
        self.assertEqual(b_list2, None)

        # category filter
        self.assertEqual(f_type, 'category')

        # one for each book-category combo
        self.assertEqual(cats.count(), 2)

        # check the selected category name
        self.assertEqual(this_cat, cat.name)

        # check the header string
        self.assertEqual(header, 'Genre: ' + cat.name)

        # no second header
        self.assertEqual(header2, '')

    def test_home_show_books_mybooks(self):
        """Test the `home.showBooks` view using the My Books book
        filter. It should return a template with the books queryset
        containing only the books lent by the logged in user.
        """
        with self.client.session_transaction() as session:
            # fake the login by adding a session variable
            session['email'] = 'admin@catalog.com'

        user = User.query.filter_by(email='admin@catalog.com').one()
        books = Book.query.filter_by(lender=user).all()

        response = self.client.get('/books/mybooks/')

        self.assert_200(response)
        self.assert_template_used('books.html')

        b_list = self.get_context_variable('books')
        b_list2 = self.get_context_variable('books2')
        f_type = self.get_context_variable('f_type')
        header = self.get_context_variable('header')
        header2 = self.get_context_variable('header2')

        # 2 books lent by user
        self.assertEqual(len(b_list), 2)

        # check book objects match
        self.assertEqual(b_list[0], books[0])
        self.assertEqual(b_list[1], books[1])

        # no books yet borrowed
        self.assertEqual(len(b_list2), 0)

        # My Books filter
        self.assertEqual(f_type, 'mybooks')

        # check header string
        self.assertEqual(header, 'Books You\'ve Lent')

        # secondary header (will not be displayed in template
        # since there are no books borrowed by user)
        self.assertEqual(header2, 'Books You\'ve Borrowed')

    def test_home_show_books_favorites(self):
        """Test the `home.showBooks` view using the Favorites book
        filter. It should return a template with the books queryset
        containing only the books marked as favorite by the user.
        """
        with self.client.session_transaction() as session:
            # fake the login by adding a session variable
            session['email'] = 'admin@catalog.com'

        response = self.client.get('/books/favorites/')

        self.assert_200(response)
        self.assert_template_used('books.html')

        b_list = self.get_context_variable('books')
        b_list2 = self.get_context_variable('books2')
        f_type = self.get_context_variable('f_type')
        header = self.get_context_variable('header')
        header2 = self.get_context_variable('header2')

        # no books yet marked favorite
        self.assertEqual(len(b_list), 0)

        # no second book list
        self.assertEqual(b_list2, None)

        # favorites filter
        self.assertEqual(f_type, 'favorites')

        # check header string
        self.assertEqual(header, 'Your Favorite Books')

        # no secondary header
        self.assertEqual(header2, '')

    def test_home_search_books_get(self):
        """Test the `home.searchBooks` view in GET mode.
        """
        response = self.client.get('/books/search/')

        self.assert200(response)
        self.assert_template_used('search.html')

        form = self.get_context_variable('form')
        cats = self.get_context_variable('categories')
        b_list = self.get_context_variable('books')

        # make sure we have the right form
        self.assertEqual(type(form), SearchForm)

        # number of categories should be right
        self.assertEqual(cats.count(), 2)

        # no search performed, so no book list
        self.assertEqual(b_list, None)

    def test_home_search_books_post(self):
        """Test the `home.searchBooks` view in POST mode
        (i.e.: conduct a book search).
        """
        url = '/books/search/'
        book = Book.query.filter_by(title='Rarnaby Budge').one()

        searchterm = 'dikkens'
        response = self.client.post(
            url,
            data={
                'searchterm': searchterm
            },
            follow_redirects=True
        )

        self.assert200(response)
        self.assert_template_used('search.html')

        form = self.get_context_variable('form')
        cats = self.get_context_variable('categories')
        b_list = self.get_context_variable('books')

        # make sure we have the right form
        self.assertEqual(type(form), SearchForm)

        # check the number of categories
        self.assertEqual(cats.count(), 2)

        # one book should match the search parameters
        self.assertEqual(len(b_list), 1)

        # the book should be the correct one
        self.assertEqual(b_list[0], book)

    def test_home_add_book_get(self):
        """Test the `home.addBook` view in GET mode.
        """
        url = '/books/add/'
        response = self.client.get(url)

        self.assert_redirects(
            response, '/login_required/?next=' + urllib.quote_plus(url))

        with self.client.session_transaction() as session:
            # fake the login by adding a session variable
            session['username'] = 'admin'

        response = self.client.get(url)

        self.assert200(response)
        self.assert_template_used('add_book.html')

        form = self.get_context_variable('form')
        form_action = self.get_context_variable('form_action')
        action = self.get_context_variable('action')

        # check that we have the right form
        self.assertEqual(type(form), BookForm)

        # the action variable should be 'add'
        self.assertEqual(action, 'add')

        # the form action should be pointing to home.addBook
        self.assertEqual(form_action, url)

    def test_home_add_book_post(self):
        """Test the `home.addBook` view in POST mode
        (i.e.: add a book using the form).
        """
        url = '/books/add/'
        category = Category.query.filter_by(name='Serious Books').one()

        with self.client.session_transaction() as session:
            # fake the login by adding session variables
            session['username'] = 'admin'
            session['email'] = 'admin@catalog.com'

        # submit the form with no data
        response = self.client.post(
            url,
            data={},
            follow_redirects=True
        )
        # make sure we have the right template
        self.assert_template_used('add_book.html')

        # alert user that a title is required
        self.assertIn('Title is required.', response.data)

        # alert user that an author's name is required
        self.assertIn('Author is required.', response.data)

        # alert user that at lease one category must be selected
        self.assertIn('Please choose a genre', response.data)

        # now submit the form with data
        title = 'War and Peace'
        author = 'Leo Tolstoy'
        response = self.client.post(
            url,
            data={
                'title': title,
                'author': author,
                'category': [category.id, ]
            },
            follow_redirects=True
        )

        # make sure the flash message gets shown to the user
        self.assertIn(
            'Thanks for lending your copy of <em>War and Peace</em>!',
            response.data
        )
        # make sure we're redirected to the right template
        self.assert_template_used('books.html')

        # pull up the new book
        new_book = Book.query.filter_by(title='War and Peace').one()

        # titles should match
        self.assertEqual(new_book.title, title)

        # authors should match
        self.assertEqual(new_book.author, author)

        # book should have the right category
        self.assertIn(category, new_book.category)

    def test_home_edit_book_get(self):
        """Test the `home.editBook` view in GET mode.
        """

        # try to edit a book without logging in
        book = Book.query.filter_by(title='Rarnaby Budge').one()
        url = '/books/' + str(book.id) + '/edit/'
        response = self.client.get(url)

        # user should be redirected to the login process
        self.assert_redirects(
            response, '/login_required/?next=' + urllib.quote_plus(url))

        with self.client.session_transaction() as session:
            # fake the login by adding a session variable
            session['username'] = 'admin'
            session['email'] = 'admin@catalog.com'

        # try (and fail) to edit a non-existent book
        response = self.client.get('/books/8675309/edit/')
        # user should be redirected rather than shown the form
        self.assert_redirects(response, '/books/')

        response = self.client.get(url)

        # now that we're logged in, show the form
        self.assert200(response)
        # make sure we have the right template
        self.assert_template_used('add_book.html')

        form = self.get_context_variable('form')
        form_action = self.get_context_variable('form_action')
        action = self.get_context_variable('action')
        delete_url = self.get_context_variable('delete_url')
        b = self.get_context_variable('book')

        # make sure we have the right form
        self.assertEqual(type(form), BookForm)

        # action variable should be 'edit'
        self.assertEqual(action, 'edit')

        # form action should point to editBook
        self.assertEqual(form_action, url)

        # view should provide a url for deleting the book
        self.assertEqual(delete_url, '/books/' + str(book.id) + '/delete/')

        # make sure we have the right book's data in the form
        self.assertEqual(b, book)

    def test_home_edit_book_post(self):
        """Test the `home.editBook` view in POST mode
        (i.e.: edit a book using the form).
        """
        book = Book.query.filter_by(title='Rarnaby Budge').one()
        url = '/books/' + str(book.id) + '/edit/'
        category = Category.query.filter_by(name='Serious Books').one()

        with self.client.session_transaction() as session:
            # fake the login by adding a session variable
            session['username'] = 'admin'
            session['email'] = 'admin@catalog.com'

        synopsis = 'A very silly book.'
        # StringIO creates an in-memory file buffer from text
        # this is sufficient for testing form-based file uploads
        picture = (StringIO('Rarnaby Budge'), 'book.png')
        response = self.client.post(
            url,
            data={
                'title': book.title,
                'author': book.author,
                'category': [category.id, ],
                'synopsis': synopsis,
                'picture': picture
            },
            follow_redirects=True
        )

        # make sure the user is shown the flash message
        self.assertIn('<em>Rarnaby Budge</em> saved.', response.data)

        # make sure we have the right template
        self.assert_template_used('books.html')

        # pull up the revised book
        new_book = Book.query.filter_by(title='Rarnaby Budge').one()

        # synopses should match
        self.assertEqual(new_book.synopsis, synopsis)

        # check the filename of the saved picture file
        # we can't know the full name because it's prepended
        # with a timestamp
        self.assertIn('_book.png', new_book.picture)

        # delete the file created by the form
        filepath = 'catalog/' + app.config['UPLOAD_FOLDER'] + '/'
        delete_test_file(filepath + new_book.picture)

    def test_home_book_info(self):
        """Test the `home.bookInfo` view. It should return a JSON
        object.
        """

        # attempt to get info for a non-existent book
        response = self.client.get('/books/8675309/info/')
        # user should be redirected
        self.assert_redirects(response, '/books/')

        book = Book.query.filter_by(title='Rarnaby Budge').one()
        response = self.client.get('/books/' + str(book.id) + '/info/')

        # make sure the server response is of JSON content type
        self.assertEqual(response.content_type, 'application/json')

        # check that we have the correct book info
        self.assertEqual(response.json['Book']['title'], book.title)
        self.assertEqual(response.json['Book']['author'], book.author)
        self.assertEqual(
            response.json['Book']['year_published'], book.year_published)
        self.assertEqual(response.json['Book']['synopsis'], book.synopsis)
        self.assertEqual(response.json['Book']['picture'], book.picture)
        self.assertEqual(
            response.json['Book']['date_added'],
            book.date_added.strftime('%a, %d %b %Y %H:%M:%S GMT')
        )
        self.assertEqual(response.json['Book']['id'], book.id)
        self.assertEqual(response.json['Book']['lender'], book.lender.email)

    def test_home_borrow_book(self):
        """Test the `home.borrowBook` view.
        """
        user = User.query.filter_by(email='admin@catalog.com').one()
        book = Book.query.filter_by(title='Rarnaby Budge').one()
        url = '/books/' + str(book.id) + '/borrow/'
        # first try to borrow a book without logging in
        response = self.client.get(url)

        # user should be redirected to the login process
        self.assert_redirects(
            response, '/login_required/?next=' + urllib.quote_plus('/books/'))

        with self.client.session_transaction() as session:
            # fake the login by adding session variables
            session['username'] = 'admin'
            session['email'] = 'admin@catalog.com'

        # now try to borrow a non-existent book
        response = self.client.get('/books/8675309/borrow/')
        # user should be redirected
        self.assert_redirects(response, '/books/')
        # no book has been borrowed
        self.assertRaises(
            NoResultFound,
            BookBorrower.query.filter_by(borrower=user).one
        )

        # now do it for real
        response = self.client.get(url)
        self.assert_redirects(response, '/books/')

        today = dt.datetime.today()
        due_date = today + dt.timedelta(days=30)
        due_date_str = due_date.strftime('%m/%d/%Y')

        bb = BookBorrower.query.filter_by(borrower=user).one()
        # check that the book is the right one
        self.assertEqual(bb.book_id, book.id)

        # check the due date
        self.assertEqual(bb.due_date, due_date.date())

        # check the book has not been returned
        self.assertFalse(bb.returned)

        msg = 'You have borrowed <em>' + book.title + '</em>. '
        msg += 'It is due back by ' + due_date_str + '.'
        response = self.client.get('/books/')
        # make sure user sees the flash message
        self.assertIn(msg, response.data)

    def test_home_return_book(self):
        """Test the `home.returnBook` view.
        """
        user = User.query.filter_by(email='admin@catalog.com').one()
        book = Book.query.filter_by(title='Rarnaby Budge').one()

        # first try to return a book without logging in
        url = '/books/' + str(book.id) + '/return/'
        response = self.client.get(url)

        # user should be redirected to the login process
        self.assert_redirects(
            response, '/login_required/?next=' + urllib.quote_plus('/books/'))

        with self.client.session_transaction() as session:
            # fake the login by adding session variables
            session['username'] = 'admin'
            session['email'] = 'admin@catalog.com'

        # now try to return a non-existent book
        response = self.client.get('/books/8675309/return/')
        # user should be redirected
        self.assert_redirects(response, '/books/')

        # now try to return a book that isn't checked out
        response = self.client.get(url)
        # user should be redirected
        self.assert_redirects(response, '/books/')

        today = dt.datetime.today()
        due_date = today + dt.timedelta(days=30)
        # check out the book
        bb = BookBorrower(book_id=book.id, user_id=user.id, due_date=due_date)
        db.session.add(bb)
        db.session.commit()

        response = self.client.get(url, follow_redirects=True)

        revised_bb = BookBorrower.query.filter_by(id=bb.id).one()
        msg = '<em>' + book.title + '</em> returned successfully.'

        # book should be marked as returned
        self.assertTrue(revised_bb.returned)

        # make sure user sees the flash message
        self.assertIn(msg, response.data)

    def test_home_review_book_get_not_reviewed(self):
        """Test the `home.reviewBook` view. This test is for
        a user who has not yet reviewed the book in question.
        """
        book = Book.query.filter_by(title='Rarnaby Budge').one()

        # first try to review a book without logging in
        url = '/books/' + str(book.id) + '/review/'
        response = self.client.get(url)

        # user should be redirected
        self.assert_redirects(
            response, '/login_required/?next=' + urllib.quote_plus('/books/'))

        with self.client.session_transaction() as session:
            # fake the login by adding session variables
            session['username'] = 'admin'
            session['email'] = 'admin@catalog.com'

        # next try to review a non-existent book
        response = self.client.get('/books/8675309/review/')
        # user should be redirected
        self.assert_redirects(response, '/books/')

        # now we're logged in and the book is real, so display the form
        response = self.client.get(url)
        self.assert200(response)
        # make sure we have the right template
        self.assert_template_used('review.html')

        form = self.get_context_variable('form')
        b = self.get_context_variable('book')

        # make sure we have the right form
        self.assertEqual(type(form), ReviewForm)

        # makee sure we're reviewing the book we want
        self.assertEqual(b, book)

    def test_home_review_book_get_reviewed(self):
        """Test the `home.reviewBook` view. This test is for
        a user who has already reviewed the book in question.
        """
        book = Book.query.filter_by(title='Rarnaby Budge').one()
        user = User.query.filter_by(email='admin@catalog.com').one()
        url = '/books/' + str(book.id) + '/review/'

        with self.client.session_transaction() as session:
            # fake the login by adding session variables
            session['username'] = 'admin'
            session['email'] = 'admin@catalog.com'

        # rate the book
        br = BookRating(
            book_id=book.id, user_id=user.id, rating=3.2, review='It rocked.')
        db.session.add(br)
        db.session.commit()

        response = self.client.get(url)
        # same page should still load
        self.assert200(response)
        self.assert_template_used('review.html')

        form = self.get_context_variable('form')
        b = self.get_context_variable('book')

        # now the form should be missing from the template
        self.assertEqual(form, None)

        # make sure we still have the right book
        self.assertEqual(b, book)

        # make sure the user sees the reviewed message
        self.assertIn('You have already reviewed this book.', response.data)

    def test_home_review_book_post(self):
        """Test the `home.reviewBook` view. This test is for
        posting a book review using the form.
        """
        book = Book.query.filter_by(title='Rarnaby Budge').one()
        user = User.query.filter_by(email='admin@catalog.com').one()

        url = '/books/' + str(book.id) + '/review/'

        with self.client.session_transaction() as session:
            # fake the login by adding session variables
            session['username'] = 'admin'
            session['email'] = 'admin@catalog.com'

        response = self.client.post(
            url,
            data={
                'rating': 3.2,
                'review': 'It rocked.'
            },
            follow_redirects=True
        )

        # make sure the user sees the flash message
        self.assertIn(
            'Thanks for reviewing <em>Rarnaby Budge</em>!', response.data)

        # make sure we're redirected to the books list
        self.assert_template_used('books.html')
        # pull up the new review
        br = BookRating.query.filter_by(book_id=book.id).one()

        # user id should match
        self.assertEqual(br.user_id, user.id)

        # rating should match
        self.assertEqual(float(br.rating), 3.2)

        # review text should match
        self.assertEqual(br.review, 'It rocked.')

    def test_home_favorite_book(self):
        """Test the `home.favoriteBook` view.
        """
        book = Book.query.filter_by(title='Rarnaby Budge').one()
        user = User.query.filter_by(email='admin@catalog.com').one()

        # try to mark the book favorite without logging in
        url = '/books/' + str(book.id) + '/favorite/'
        response = self.client.get(url)

        # user should be redirected
        self.assert_redirects(
            response, '/login_required/?next=' + urllib.quote_plus('/books/'))
        # no favorite saved
        revised_book = Book.query.filter_by(title='Rarnaby Budge').one()
        self.assertNotIn(user, revised_book.favorite)

        with self.client.session_transaction() as session:
            # fake the login by adding session variables
            session['username'] = 'admin'
            session['email'] = 'admin@catalog.com'

        # now try to favorite a non-existent book
        response = self.client.get('/books/8675309/favorite/')
        # user should be redirected
        self.assert_redirects(response, '/books/')
        # no favorite saved
        revised_book = Book.query.filter_by(title='Rarnaby Budge').one()
        self.assertNotIn(user, revised_book.favorite)

        # now for reals
        response = self.client.get(url)
        self.assert_redirects(response, '/books/')

        # new favorite saved
        revised_book = Book.query.filter_by(title='Rarnaby Budge').one()
        self.assertIn(user, revised_book.favorite)

    def test_home_delete_book(self):
        """Test the `home.deleteBook` view.
        """
        book = Book.query.filter_by(title='Rarnaby Budge').one()

        # first try to delete a book without logging in
        url = '/books/' + str(book.id) + '/delete/'
        response = self.client.post(url)

        # user should be redirected
        self.assert_redirects(
            response, '/login_required/?next=' + urllib.quote_plus('/books/'))
        # book still there
        self.assertEqual(
            int(Book.query.filter_by(title='Rarnaby Budge').count()), 1)

        with self.client.session_transaction() as session:
            # fake the login by adding session variables
            session['username'] = 'admin'
            session['email'] = 'admin@catalog.com'

        # now try to delete a non-existent book
        response = self.client.post('/books/8675309/delete/')
        # user should be redirected
        self.assert_redirects(response, '/books/')
        # book still there
        self.assertEqual(
            int(Book.query.filter_by(title='Rarnaby Budge').count()), 1)

        # now for real
        response = self.client.post(url)
        self.assert_redirects(response, '/books/')

        # book is gone
        self.assertRaises(
            NoResultFound,
            Book.query.filter_by(title='Rarnaby Budge').one
        )
        response = self.client.get('/books/')
        # make sure user sees the flash message
        self.assertIn('<em>Rarnaby Budge</em> removed.', response.data)

    def test_home_delete_book_wrong_user(self):
        """Test the `home.deleteBook` view. This time, the wrong user
        is trying to delete the book (you can only delete your own books).
        """
        category = Category.query.filter_by(name='Silly Books').one()
        user = User.query.filter_by(email='admin@catalog.com').one()

        # create a new book and user
        book = Book(
            title='David Coperfield',
            author='Edmund Wells',
            year_published=1967,
            category=[category, ],
            lender=user
        )
        user2 = User(name='customer', email='customer@bookshopsketch.com')

        db.session.add(book)
        db.session.add(user2)
        db.session.commit()

        with self.client.session_transaction() as session:
            # fake the login by adding session variables
            session['username'] = user2.name
            session['email'] = user2.email

        url = '/books/' + str(book.id) + '/delete/'
        response = self.client.post(url)
        # user should be redirected, and book still exists
        self.assert_redirects(response, '/books/')
        revised_book = Book.query.filter_by(title='David Coperfield').one()
        self.assertEqual(revised_book.author, 'Edmund Wells')

    def test_home_books_api_json(self):
        """Test the `home.booksAPI` view. This test is for JSON
        output.
        """
        # get recent books in JSON
        url = '/books/API/'
        response = self.client.get(url)
        # check JSON output; it should match the books_json string above
        self.assertEqual(books_json, response.data)
        # response should have the Content-Type header `application/json`
        self.assertEqual(response.content_type, 'application/json')

    def test_home_books_api_xml(self):
        """Test the `home.booksAPI` view. This test is for XML
        output.
        """
        # get all books in XML
        url = '/books/API/all/XML/'
        response = self.client.get(url)
        # check XML output; it should match the books_xml string above
        self.assertEqual(books_xml, response.data)
        # response should have the Content-Type header `application/xml`
        self.assertEqual(
            response.content_type, 'application/xml; charset=utf-8')

    def test_home_books_api_atom(self):
        """Test the `home.booksAPI` view. This test is for XML
        output in Atom Syndication Format.
        """
        # get books in a category in Atom
        url = '/books/API/category/Silly%20Books/Atom/'
        response = self.client.get(url)

        # because the Atom feed includes a date/time stamp, we need to
        # pull that info from the response data and insert it into our
        # test variable
        root = ET.fromstring(response.data)
        updated = root.find('{http://www.w3.org/2005/Atom}updated')
        revised_atom = re.sub(r'---updated---', updated.text, books_atom)

        # check Atom output against modified books_atom string above
        self.assertEqual(revised_atom, response.data)
        # response should have the Content-Type header `application/atom+xml`
        self.assertEqual(
            response.content_type, 'application/atom+xml; charset=utf-8')

    def test_home_books_api_rss(self):
        """Test the `home.booksAPI` view. This test is for XML
        output in RSS format.
        """
        # get all books in RSS
        url = '/books/API/all/RSS/'
        response = self.client.get(url)

        # because the RSS feed includes a date/time stamp, we need to
        # pull that info from the response data and insert it into our
        # test variable
        root = ET.fromstring(response.data)
        channel = root.find('channel')
        updated = channel.find('pubDate')
        revised_rss = re.sub(r'---updated---', updated.text, books_rss)

        # check RSS output against modified books_rss string above
        self.assertEqual(revised_rss, response.data)
        # response should have the Content-Type header `application/rss+xml`
        self.assertEqual(
            response.content_type, 'application/rss+xml; charset=utf-8')

    def test_home_media(self):
        """Test the `home.media` view, which is used for displaying
        user-uploaded static files (just book cover art in this app)
        """
        user = User.query.filter_by(email='admin@catalog.com').one()
        category = Category.query.filter_by(name='Silly Books').one()

        # StringIO creates an in-memory file buffer from text
        # this is sufficient for testing form-based file uploads
        picture = (StringIO('Another classic Wells'), 'book.png')

        with self.client.session_transaction() as session:
            # fake the login by adding session variables
            session['username'] = user.name
            session['email'] = user.email

        url = '/books/add/'
        title = 'Grate Expectations'
        author = 'Edmund Wells'
        year_published = 1967
        synopsis = 'Also by Edmund Wells'

        # in order to test this we need to upload a media file using
        # the `home.addBooks` view
        response = self.client.post(
            url,
            data={
                'title': title,
                'author': author,
                'category': [category.id, ],
                'synopsis': synopsis,
                'picture': picture,
                'year_published': year_published
            },
            follow_redirects=True
        )

        # calling a non-existent media file should generate a 404 error
        response = self.client.get('/media/nonesuch.png')
        self.assert404(response)
        new_book = Book.query.filter_by(title='Grate Expectations').one()
        # get the correct file
        response = self.client.get('/media/' + new_book.picture)
        # found it!
        self.assert200(response)
        # delete the file now that we're done
        filepath = 'catalog/' + app.config['UPLOAD_FOLDER'] + '/'
        delete_test_file(filepath + new_book.picture)

    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
     TEST AUTH VIEWS
    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

    def test_auth_show_login(self):
        """Test the `auth.showLogin` view, which is used to display the
        login.html template containing the Google+ and Facebook sign-in
        buttons.
        """
        response = self.client.get('/login/')
        self.assert200(response)

        with self.client.session_transaction() as session:
            # fake the login by adding a session variable
            session_state = session['state']

        state = self.get_context_variable('STATE')
        # make sure we have the right template
        self.assert_template_used('login.html')
        # check that the STATE variable is the right length
        self.assertEqual(len(state), 32)
        # make sure STATE var matches the session var
        self.assertEqual(session_state, state)

    def test_auth_login_required(self):
        """Test the `auth.showLogin` view, which is used to display the
        "login required" message with a link to sign in.
        """
        response = self.client.get('/login_required/')
        self.assert200(response)
        # make sure we have the right template
        self.assert_template_used('login_required.html')

    def test_auth_gconnect_generate_redirect_uri(self):
        """Ensure that Google sign-in api generates a proper OAuth2.0
        redirect URI.
        """
        # if we're not using Google+ for signin, don't run the test
        if (app.config['USE_GOOGLE_SIGNIN'] == False):
            return

        gclient_id = get_google_client_id()
        # hit the login page to get the STATE variable
        response = self.client.get('/login/')
        self.assert200(response)

        with self.client.session_transaction() as session:
            # fake the login by adding a session variable
            session_state = session['state']

        # create testing JSON config files
        save_google_secrets_test_files()

        url = '/oauth2callback?state=' + session_state
        url += '&secret=instance/client_secrets_test.json'
        url += '&id=110169484474386276334&issued='
        url += gclient_id
        # call the `auth.gconnect` view to get the uri
        response = self.client.get(url)

        # the redirect URI is in the Location header
        code_url = response.headers['Location']
        # pull apart the URI and lok for the "client_id" parameter
        q_dict = dict(urlparse.parse_qsl(urlparse.urlsplit(code_url).query))
        # parameter should match our Google client_id
        self.assertEqual(q_dict['client_id'], gclient_id)
        # make sure other parameters match expected values
        self.assertEqual(
            q_dict['scope'],
            'https://www.googleapis.com/auth/plus.profile.emails.read'
        )
        self.assertEqual(q_dict['include_granted_scopes'], 'true')
        self.assertEqual(q_dict['access_type'], 'offline')
        self.assertEqual(q_dict['response_type'], 'code')

        # delete the testing JSON files
        delete_test_file('instance/client_secrets_test.json')
        delete_test_file('instance/client_secrets_bogus_test.json')

    def test_auth_gconnect(self):
        """Using mocked server responses, ensure user can connect to
        the application using Google sign-in api.
        """
        # if we're not using Google+ for signin, don't run the test
        if (app.config['USE_GOOGLE_SIGNIN'] == False):
            return

        user = User.query.filter_by(email='admin@catalog.com').one()
        # hit the login page to get the STATE variable
        response = self.client.get('/login/')
        self.assert200(response)

        with self.client.session_transaction() as session:
            # get the session, make sure the STATE variable gets saved
            session_state = session['state']

        # create testing JSON config files
        save_google_secrets_test_files()

        url = '/oauth2callback?state=' + session_state + '&code=8675309'
        url += '&next=/books/&secret=instance/client_secrets_test.json'
        url += '&id=110169484474386276334&issued='
        url += get_google_client_id()
        # the `client_secrets_test.json` contains an internal URL
        # which points to the `test.getAccessToken` view
        # this is our pretend Google+ signin server
        response = self.client.get(url, follow_redirects=True)
        self.assert_template_used('books.html')
        # make sure user sees the flash message
        self.assertIn('You are now logged in as admin', response.data)

        with self.client.session_transaction() as session:
            # pull new session vars, make sure they match
            self.assertEqual(session['username'], user.name)
            self.assertEqual(session['email'], user.email)
            self.assertEqual(session['picture'], 'http://catalog.com/user.png')
            self.assertEqual(session['provider'], 'google')
            self.assertEqual(session['gplus_id'], '110169484474386276334')
            self.assertEqual(session['user_id'], user.id)

        # delete the testing JSON files
        delete_test_file('instance/client_secrets_test.json')
        delete_test_file('instance/client_secrets_bogus_test.json')

    def test_auth_gconnect_new_user(self):
        """Using mocked server responses, ensure user can connect to
        the application using Google sign-in api. This test is for a
        new user to make sure it gets added to the DB.
        """
        # if we're not using Google+ for signin, don't run the test
        if (app.config['USE_GOOGLE_SIGNIN'] == False):
            return

        # delete our lone user for this test (sorry, dude)
        user = User.query.filter_by(email='admin@catalog.com').one()
        db.session.delete(user)
        db.session.commit()
        self.assertRaises(
            NoResultFound, User.query.filter_by(email='admin@catalog.com').one)

        # hit the login page to get the STATE variable
        response = self.client.get('/login/')
        self.assert200(response)

        with self.client.session_transaction() as session:
            # get the session, make sure the STATE variable gets saved
            session_state = session['state']

        # create testing JSON config files
        save_google_secrets_test_files()

        url = '/oauth2callback?state=' + session_state + '&code=8675309'
        url += '&next=/books/&secret=instance/client_secrets_test.json'
        url += '&id=110169484474386276334&issued='
        url += get_google_client_id()
        # the `client_secrets_test.json` contains an internal URL
        # which points to the `test.getAccessToken` view
        # this is our pretend Google+ signin server
        response = self.client.get(url, follow_redirects=True)

        # pull up the new user and make sure the info is right
        new_user = User.query.filter_by(email='admin@catalog.com').one()
        self.assertEqual(new_user.name, 'admin')
        self.assertEqual(new_user.email, 'admin@catalog.com')
        self.assertEqual(new_user.picture, 'http://catalog.com/user.png')

        # delete the testing JSON files
        delete_test_file('instance/client_secrets_test.json')
        delete_test_file('instance/client_secrets_bogus_test.json')

    def test_auth_gconnect_invalid_state(self):
        """Using mocked server responses, ensure user can connect to
        the application using Google sign-in api. This test is to make
        sure that if the STATE variable is missing the process aborts.
        """
        # if we're not using Google+ for signin, don't run the test
        if (app.config['USE_GOOGLE_SIGNIN'] == False):
            return

        with self.client.session_transaction() as session:
            # add a fake STATE var
            session['state'] = 'splunge'

        # create testing JSON config files
        save_google_secrets_test_files()

        url = '/oauth2callback?next=/books/&secret=instance'
        url += '/client_secrets_bogus_test.json&id=&issued='
        response = self.client.get(url)
        # make sure we get an error message, properly formatted
        self.assertIn('Invalid state parameter', response.data)
        self.assertEqual(response.content_type, 'application/json')

        # delete the testing JSON files
        delete_test_file('instance/client_secrets_test.json')
        delete_test_file('instance/client_secrets_bogus_test.json')

    def test_auth_gconnect_flow_error(self):
        """Using mocked server responses, ensure user can connect to
        the application using Google sign-in api. This test is to make
        sure that Google does not return a redirect URI if the
        `access_token` parameter doesn't exist in our request. See the
        `test.getWrongAccessToken` view.
        """
        # if we're not using Google+ for signin, don't run the test
        if (app.config['USE_GOOGLE_SIGNIN'] == False):
            return

        # hit the login page to get the STATE variable
        response = self.client.get('/login/')
        self.assert200(response)

        with self.client.session_transaction() as session:
            # get the session, make sure the STATE variable gets saved
            session_state = session['state']

        # create testing JSON config files
        save_google_secrets_test_files()

        url = '/oauth2callback?state=' + session_state + '&code=8675309'
        url += '&next=/books/&secret=instance/client_secrets_bogus_test.json'
        url += '&id=110169484474386276334&issued='
        url += get_google_client_id()
        # the `client_secrets_bogus_test.json` contains an internal URL
        # which points to the `test.getWrongAccessToken` view, which is
        # missing the access_token parameter
        response = self.client.get(url)
        # make sure we get the error message, properly formatted
        self.assertIn(
            'Failed to upgrade the authorization code:', response.data)
        self.assertEqual(response.content_type, 'application/json')

        # delete the testing JSON files
        delete_test_file('instance/client_secrets_test.json')
        delete_test_file('instance/client_secrets_bogus_test.json')

    def test_auth_gconnect_bad_userid(self):
        """Using mocked server responses, ensure user can connect to
        the application using Google sign-in api. This test is to make
        sure that the signin process aborts if the returned Google+
        user id doesn't match the expected value.
        """
        # if we're not using Google+ for signin, don't run the test
        if (app.config['USE_GOOGLE_SIGNIN'] == False):
            return

        # hit the login page to get the STATE variable
        response = self.client.get('/login/')
        self.assert200(response)

        with self.client.session_transaction() as session:
            # get the session, make sure the STATE variable gets saved
            session_state = session['state']

        # create testing JSON config files
        save_google_secrets_test_files()

        url = '/oauth2callback?state=' + session_state + '&code=8675309'
        url += '&next=/books/&secret=instance/client_secrets_test.json'
        url += '&id=8675309&issued=' + get_google_client_id()
        # the `client_secrets_test.json` contains an internal URL
        # which points to the `test.getAccessToken` view
        # this is our pretend Google+ signin server; this time we're
        # deliberately passing the wrong user id in the `id` parameter
        response = self.client.get(url)
        # make sure user sees the error message, properly formatted
        self.assertIn(
            'Token\'s user ID doesn\'t match given user ID.', response.data)
        self.assertEqual(response.content_type, 'application/json')

        # delete the testing JSON files
        delete_test_file('instance/client_secrets_test.json')
        delete_test_file('instance/client_secrets_bogus_test.json')

    def test_auth_gconnect_bad_clientid(self):
        """Using mocked server responses, ensure user can connect to
        the application using Google sign-in api. This test is to make
        sure that the signin process aborts if the returned Google+
        client id doesn't match the expected value.
        """
        # if we're not using Google+ for signin, don't run the test
        if (app.config['USE_GOOGLE_SIGNIN'] == False):
            return

        # hit the login page to get the STATE variable
        response = self.client.get('/login/')
        self.assert200(response)

        with self.client.session_transaction() as session:
            # get the session, make sure the STATE variable gets saved
            session_state = session['state']

        # create testing JSON config files
        save_google_secrets_test_files()

        url = '/oauth2callback?state=' + session_state + '&code=8675309'
        url += '&next=/books/&secret=instance/client_secrets_test.json'
        url += '&id=110169484474386276334&issued=etheltheaardvark'
        # the `client_secrets_test.json` contains an internal URL
        # which points to the `test.getAccessToken` view
        # this is our pretend Google+ signin server; this time we're
        # deliberately passing the wrong client id in the `issued`
        # parameter
        response = self.client.get(url)
        # make sure user sees the error message, properly formatted
        self.assertIn(
            'Token\'s client ID doesn\'t match app\'s.', response.data)
        self.assertEqual(response.content_type, 'application/json')

        # delete the testing JSON files
        delete_test_file('instance/client_secrets_test.json')
        delete_test_file('instance/client_secrets_bogus_test.json')

    def test_auth_gconnect_already_logged_in(self):
        """Using mocked server responses, ensure user can connect to
        the application using Google sign-in api. This test is to make
        sure that the signin process aborts cleanly if the user is
        already signed into the app.
        """
        # if we're not using Google+ for signin, don't run the test
        if (app.config['USE_GOOGLE_SIGNIN'] == False):
            return

        # hit the login page to get the STATE variable
        response = self.client.get('/login/')
        self.assert200(response)

        with self.client.session_transaction() as session:
            # get the session, make sure the STATE variable gets saved
            # also add session variables to simulate being logged in
            session_state = session['state']
            session['credentials'] = 'gospel according to charlie drake'
            session['gplus_id'] = '110169484474386276334'

        # create testing JSON config files
        save_google_secrets_test_files()

        url = '/oauth2callback?state=' + session_state + '&code=8675309'
        url += '&next=/books/&secret=instance/client_secrets_test.json'
        url += '&id=110169484474386276334&issued=' + get_google_client_id()
        # the `client_secrets_test.json` contains an internal URL
        # which points to the `test.getAccessToken` view
        # this is our pretend Google+ signin server
        response = self.client.get(url)
        # make sure user sees the message, properly formatted
        self.assertIn(
            'Current user is already connected', response.data)
        self.assertEqual(response.content_type, 'application/json')
        # in this case we're not really reporting an error, just info
        self.assert200(response)

        # delete the testing JSON files
        delete_test_file('instance/client_secrets_test.json')
        delete_test_file('instance/client_secrets_bogus_test.json')

    def test_auth_gdisconnect(self):
        """Ensure user can log out of the app if they are signed in
        through Google+.
        """
        # if we're not using Google+ for signin, don't run the test
        if (app.config['USE_GOOGLE_SIGNIN'] == False):
            return

        user = User.query.filter_by(email='admin@catalog.com').one()

        with self.client.session_transaction() as session:
            # store session variables to simulate being logged in
            session['credentials'] = '{"access_token": "goodtoken"}'
            session['gplus_id'] = '110169484474386276334'
            session['provider'] = 'google'
            session['username'] = user.name
            session['email'] = user.email
            session['picture'] = 'http://catalog.com/user.png'
            session['user_id'] = user.id

        response = self.client.get('/disconnect/', follow_redirects=True)
        self.assert200(response)
        # make sure we're redirected back to the home page
        self.assert_template_used('index.html')
        # make sure user sees the flash message
        self.assertIn('You have been successfully logged out.', response.data)

        with self.client.session_transaction() as session:
            # check that the session variables have been removed
            self.assertNotIn('credentials', session)
            self.assertNotIn('gplus_id', session)
            self.assertNotIn('provider', session)
            self.assertNotIn('username', session)
            self.assertNotIn('email', session)
            self.assertNotIn('picture', session)
            self.assertNotIn('user_id', session)

    def test_auth_fbconnect_invalid_state(self):
        """Ensure user can connect to the application using Facebook
        sign-in api. This test is to make sure that the signin process
        aborts if the STATE variable is incorrect.
        """
        # if we're not using Facebook for signin, don't run the test
        if (app.config['USE_FACEBOOK_SIGNIN'] == False):
            return

        with self.client.session_transaction() as session:
            # save a bogus STATE value in session
            session['state'] = 'splunge'

        url = '/fbconnect'
        response = self.client.post(url)
        # make sure user sees the error message, properly formatted
        self.assertIn('Invalid state parameter', response.data)
        self.assertEqual(response.content_type, 'application/json')

    def test_auth_fbconnect(self):
        """Ensure user can connect to the application using Facebook
        sign-in api. Uses mocked server responses similar to the Google
        process.
        """
        # if we're not using Facebook for signin, don't run the test
        if (app.config['USE_FACEBOOK_SIGNIN'] == False):
            return

        user = User.query.filter_by(email='admin@catalog.com').one()
        # hit the login page to get the STATE variable
        response = self.client.get('/login/')
        self.assert200(response)

        with self.client.session_transaction() as session:
            # get the session, make sure the STATE variable gets saved
            session_state = session['state']

        url = '/fbconnect?state=' + session_state
        data = '{hereisyourfacebooktoken}'
        # simulate Facebook signin process; see `test.fbGetToken` view
        response = self.client.post(url, data=data, follow_redirects=True)
        self.assert200(response)
        # make sure we get a success message back
        self.assertIn('Success', response.data)

        with self.client.session_transaction() as session:
            # check the session vars
            self.assertEqual(session['provider'], 'facebook')
            self.assertEqual(session['username'], user.name)
            self.assertEqual(session['email'], user.email)
            self.assertEqual(session['facebook_id'], user.name)
            self.assertEqual(session['access_token'], data)
            self.assertEqual(session['picture'], 'http://catalog.com/user.png')
            self.assertEqual(session['user_id'], user.id)

        response = self.client.get('/books/')
        # make sure user sees the flash message
        self.assertIn('You are now logged in as admin', response.data)

    def test_auth_fbconnect_new_user(self):
        """Ensure user can connect to the application using Facebook
        sign-in api. Uses mocked server responses similar to the Google
        process. This test is for a new user.
        """
        # if we're not using Facebook for signin, don't run the test
        if (app.config['USE_FACEBOOK_SIGNIN'] == False):
            return

        # delete our lone user for this test (sorry, dude)
        user = User.query.filter_by(email='admin@catalog.com').one()
        db.session.delete(user)
        db.session.commit()
        self.assertRaises(
            NoResultFound, User.query.filter_by(email='admin@catalog.com').one)

        # hit the login page to get the STATE variable
        response = self.client.get('/login/')
        self.assert200(response)

        with self.client.session_transaction() as session:
            # get the session, make sure the STATE variable gets saved
            session_state = session['state']

        url = '/fbconnect?state=' + session_state
        data = '{hereisyourfacebooktoken}'
        # simulate Facebook signin process; see `test.fbGetToken` view
        response = self.client.post(url, data=data, follow_redirects=True)

        # check that our new user exists and the info is right
        new_user = User.query.filter_by(email='admin@catalog.com').one()
        self.assertEqual(new_user.name, 'admin')
        self.assertEqual(new_user.email, 'admin@catalog.com')
        self.assertEqual(new_user.picture, 'http://catalog.com/user.png')

    def test_auth_fbdisconnect(self):
        """Ensure user can log out of the application when signed in using
        Facebook.
        """
        # if we're not using Facebook for signin, don't run the test
        if (app.config['USE_FACEBOOK_SIGNIN'] == False):
            return

        user = User.query.filter_by(email='admin@catalog.com').one()

        with self.client.session_transaction() as session:
            # set session vars to simulate being logged in
            session['provider'] = 'facebook'
            session['username'] = user.name
            session['email'] = user.email
            session['facebook_id'] = user.name
            session['picture'] = 'http://catalog.com/user.png'
            session['user_id'] = user.id

        response = self.client.get('/disconnect/', follow_redirects=True)
        self.assert200(response)
        self.assert_template_used('index.html')
        # make sure user sees the flash message
        self.assertIn('You have been successfully logged out.', response.data)

        with self.client.session_transaction() as session:
            # make sure session vars have been deleted
            self.assertNotIn('facebook_id', session)
            self.assertNotIn('provider', session)
            self.assertNotIn('username', session)
            self.assertNotIn('email', session)
            self.assertNotIn('picture', session)
            self.assertNotIn('user_id', session)

    def test_auth_disconnect_not_logged_in(self):
        """If a user is not signed in and hits the logout view, reurn
        an appropriate message.
        """
        response = self.client.get('/disconnect/', follow_redirects=True)
        # don't report an error, just info
        self.assert200(response)
        # make sure we're redirected to the home page
        self.assert_template_used('index.html')
        # make sure user sees the flash message
        self.assertIn('You were not logged in to begin with!', response.data)

    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
     TEST TEST VIEWS
    """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

    def test_test_testing_only(self):
        """Make sure the test views don't run is the testing flag is off.
        """
        app.testing = False
        response = self.client.post('/test/get_access_token/')
        self.assert_redirects(response, '/')


if __name__ == '__main__':
    unittest.main()
