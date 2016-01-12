import datetime as dt
import httplib2
import json
import os
import re
import time

from flask import (
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    send_from_directory,
    session as login_session,
    url_for
)
from sqlalchemy import or_
from sqlalchemy.orm.exc import NoResultFound
from urllib import urlencode

from . import home
from .. import app, db
from ..models import (
    Book,
    Category,
    BookBorrower,
    BookRating,
    book_favorite,
    User
)
from ..forms import BookForm, SearchForm, ReviewForm
from ..utils import (
    book_exists,
    filter_books,
    login_required,
    save_uploaded_image,
    xmlify,
    atomify,
    rssify
)


@home.route('/')
def catalogHome():
    """Handle a user's request for the app root."""
    return render_template('index.html')


@home.route('/about/')
def aboutCatalog():
    """Handle a user's request for `About LendingLibrary`."""
    return render_template('about.html')


@home.route('/books/', defaults={'bookfilter': None, 'thisCategory': None})
@home.route('/books/<bookfilter>/', defaults={'thisCategory': None})
@home.route(
    '/books/category/<thisCategory>/', defaults={'bookfilter': 'category'})
def showBooks(bookfilter, thisCategory):
    """The primary view for the LendingLibrary app, displaying a list
    of books. This single view handles a number of different use cases,
    including books tagged as Favorite by users, books lent or
    borrowed by users, as well as books by category/genre. Hence all
    the routes.
    """
    categories = Category.query.outerjoin(Category.books)
    fType = ''
    books2 = None
    header2 = ''

    books = filter_books(bookfilter, thisCategory)

    if (bookfilter == 'mybooks'):
        # show books that are either lent or borrowed by the user
        # note that this option is not available if the user is
        # not authenticated
        books2 = Book.query.filter(Book.borrower.any(
            BookBorrower.borrower == g.user)).all()
        header = 'Books You\'ve Lent'
        header2 = 'Books You\'ve Borrowed'
        fType = 'mybooks'
    elif (bookfilter == 'favorites'):
        # show books that are marked a Favorite by the user
        # note that this option is not available if the user is
        # not authenticated
        header = 'Your Favorite Books'
        fType = 'favorites'
    elif (bookfilter == 'category'):
        # show books based on their category
        # option is available to all users
        header = 'Genre: ' + thisCategory
        fType = 'category'
    else:
        # the default; show the most recent 8 books
        header = 'Recently Added Books'

    return render_template(
        'books.html',
        books=books,
        books2=books2,
        f_type=fType,
        categories=categories,
        this_category=thisCategory,
        header=header,
        header2=header2
    )


@home.route('/books/search/', methods=['GET', 'POST'])
def searchBooks():
    """View for searching books. Users can search by title, author
    or synopsis.
    """
    form = SearchForm()
    categories = Category.query.outerjoin(Category.books)
    books = None

    if (form.validate_on_submit()):
        searchterm = form.searchterm.data
        books = Book.query.filter(or_(
            Book.title.ilike('%' + searchterm + '%'),
            Book.author.ilike('%' + searchterm + '%'),
            Book.synopsis.ilike('%' + searchterm + '%')
        )).all()

    return render_template(
        'search.html',
        books=books,
        form=form,
        categories=categories
    )


@home.route('/books/add/', methods=['GET', 'POST'])
@login_required('home.addBook')
def addBook():
    """View for adding new books to the Library. Requires users to be
    authenticated.
    """
    form = BookForm()
    action = 'add'
    form_action = url_for('home.addBook')

    if (form.validate_on_submit()):
        picture = ''
        description = form.synopsis.data
        year_published = form.year_published.data
        if (form.picture.data):
            picture = save_uploaded_image(form.picture.data)

        if (app.config['USE_GOOGLE_API']):
            # if the app has enabled the Google Books API, user
            # can leave some fields in the add_book form blank
            # to be filled in by the API; specifically, the
            # year published, synopsis and cover art
            api_key = app.config['GOOGLE_API_KEY']
            query = 'intitle:' + form.title.data
            query += '+inauthor:' + form.author.data
            query_dict = {
                'q': query,
                'printType': 'books',
                'projection': 'lite',
                'key': api_key
            }
            url = (
                'https://www.googleapis.com/books/v1/volumes?%s'
                % urlencode(query_dict)
            )
            h = httplib2.Http()
            resp = h.request(url, 'GET')[1]
            result = json.loads(resp)
            if ('items' in result and len(result['items']) > 0):
                g_book = result['items'][0]['volumeInfo']
                if (picture == ''):
                    # if user has not uploaded cover art, attempt
                    # to pull it from the Google Books API
                    picture = g_book['imageLinks']['thumbnail']
                    picture = re.sub(r'&edge=curl', '', picture)
                if not (description):
                    # if user has not provided a synopsis, attempt
                    # to pull it from the Google Books API
                    try:
                        description = g_book['description']
                    except KeyError:
                        # occasionally the API does not provide a
                        # description; in this case, leave it blank
                        description = ''
                if not (year_published):
                    # if user has not provided the year published
                    # for the book, attempt to pull it from the
                    # Google Books API
                    try:
                        # usually, the publishedDate is provided as a
                        # 4-digit year; sometimes not
                        year_published = int(g_book['publishedDate'])
                    except ValueError:
                        try:
                            # if not, try to pull it from a date string
                            year_published = time.strptime(
                                g_book['publishedDate'],
                                '%Y-%m-%d')[0]
                        except:
                            # all else fails, leave it blank
                            year_published = None

        new_book = Book()
        form.populate_obj(new_book)
        new_book.lender_id = g.user.id
        new_book.picture = picture
        new_book.synopsis = description
        new_book.year_published = year_published

        db.session.add(new_book)
        db.session.commit()

        flash(
            'Thanks for lending your copy of <em>' + new_book.title + '</em>!')

        return redirect(url_for('home.showBooks'))

    return render_template(
        'add_book.html', form=form, form_action=form_action, action=action)


@home.route('/books/<int:book_id>/edit/', methods=['GET', 'POST'])
@login_required('home.editBook')
@book_exists
def editBook(book_id, **kwargs):
    """Handle the user's ability to edit a book s/he has added."""
    book = kwargs['book']
    book_pic = book.picture

    # verify that this user is the book's lender;
    # this should never come up, as the template is
    # constructed not to display an edit link for
    # users who are not the lender
    user = User.query.filter_by(email=login_session['email']).one()
    if (user != book.lender):
        # if not, redirect back to the book listing
        return redirect(url_for('home.showBooks'))

    form = BookForm(obj=book)
    action = 'edit'
    form_action = url_for('home.editBook', book_id=book_id)

    if (form.validate_on_submit()):
        form.populate_obj(book)
        db.session.add(book)
        if (form.picture.data.filename):
            book.picture = save_uploaded_image(form.picture.data)
        else:
            book.picture = book_pic
        db.session.commit()

        flash('<em>' + book.title + '</em> saved.')
        return redirect(url_for('home.showBooks'))

    return render_template(
        'add_book.html',
        form=form,
        form_action=form_action,
        action=action,
        delete_url=url_for('home.deleteBook', book_id=book.id),
        book=book
    )


@home.route('/books/<int:book_id>/info/', methods=['GET', 'POST'])
@book_exists
def bookInfo(book_id, **kwargs):
    """Return a JSON object containing a specific book's data. Used
    to display a book's info in a modal window from the book list
    page. This function should only be called through AJAX.
    """
    book = kwargs['book']

    return jsonify(Book=book.serialize)


@home.route('/books/<int:book_id>/borrow/')
@login_required()
@book_exists
def borrowBook(book_id, **kwargs):
    """Handle a user's request to borrow a book from the library. User
    must be authenticated and, as always, the requested book must exist.
    Books by default are borrowed for 30 days (or less).
    """
    book = kwargs['book']

    today = dt.datetime.today()
    due_date = today + dt.timedelta(days=30)  # 30 days...tick tock...
    due_date_str = due_date.strftime('%m/%d/%Y')
    bb = BookBorrower(book_id=book.id, user_id=g.user.id, due_date=due_date)
    db.session.add(bb)
    db.session.commit()
    msg = 'You have borrowed <em>' + book.title + '</em>. It is due back by '
    msg += due_date_str + '.'  # provide the due date to the user
    flash(msg)
    return redirect(url_for('home.showBooks'))


@home.route('/books/<int:book_id>/return/')
@login_required()
@book_exists
def returnBook(book_id, **kwargs):
    """Provide ability to return a borrowed book."""
    book = kwargs['book']
    bb = BookBorrower.query.filter_by(
        book_id=book_id, user_id=g.user.id, returned=False).one()

    if not (bb.returned):
        # assuming book has not already been returned...
        bb.returned = True
        db.session.add(bb)
        db.session.commit()

    flash('<em>' + book.title + '</em> returned successfully.')
    return redirect(url_for('home.showBooks'))


@home.route('/books/<int:book_id>/review/', methods=['GET', 'POST'])
@login_required()
@book_exists
def reviewBook(book_id, **kwargs):
    """Provide ability for users to review books."""
    book = kwargs['book']

    has_rated = BookRating.query.filter_by(rater=g.user, book_id=book.id).all()
    if (len(has_rated) > 0):
        # if the user has already reviewed this book, don't show the
        # form (i.e.: one review per user)
        form = None
    else:
        form = ReviewForm()

        if (form.validate_on_submit()):
            review = BookRating()
            review.book_id = book.id
            review.user_id = g.user.id
            review.rating = form.rating.data
            review.review = form.review.data
            db.session.add(review)
            db.session.commit()

            flash('Thanks for reviewing <em>' + book.title + '</em>!')
            return redirect(url_for('home.showBooks'))

    return render_template('review.html', form=form, book=book)


@home.route('/books/<int:book_id>/favorite/')
@login_required()
@book_exists
def favoriteBook(book_id, **kwargs):
    """Provide ability for users to mark books as favorites, in order
    to get to them more easily (via the Favorites option on the book
    list page).
    """
    book = kwargs['book']

    db.session.execute(
        book_favorite.insert().values([book.id, g.user.id, ]))
    db.session.commit()

    return redirect(url_for('home.showBooks'))


@home.route('/books/<int:book_id>/delete/')
@login_required()
@book_exists
def deleteBook(book_id, **kwargs):
    """Deleting a book in this case really means removing it from the
    Lending Library (presumably the user still owns the book). It amounts
    to the same thing, I suppose.
    """
    book = kwargs['book']

    if (book.lender == g.user):
        # aaaaand the user must also be the lender
        # no sneaking off deleting other user's books
        db.session.delete(book)
        db.session.commit()

    flash('<em>' + book.title + '</em> removed.')

    return redirect(url_for('home.showBooks'))


@home.route(
    '/books/API/',
    defaults={
        'bookfilter': None,
        'thisCategory': None,
        'apiFormat': 'JSON'
    }
)
@home.route('/books/API/<bookfilter>/', defaults={
    'thisCategory': None,
    'apiFormat': 'JSON'
})
@home.route('/books/API/<bookfilter>/<apiFormat>/', defaults={
    'thisCategory': None
})
@home.route(
    '/books/API/category/<thisCategory>/',
    defaults={'bookfilter': 'category', 'apiFormat': 'JSON'}
)
@home.route(
    '/books/API/category/<thisCategory>/<apiFormat>/',
    defaults={'bookfilter': 'category'}
)
def booksAPI(bookfilter, thisCategory, apiFormat):
    """Provide an API for, you know, lots of...um...API uses.
    In our case, the API provides a list of books, according to a
    variety of filter criteria. The output can be in JSON, Atom,
    raw XML or RSS format.
    """
    books = filter_books(bookfilter, thisCategory)

    if (apiFormat == 'XML'):
        return xmlify('book', [b.serialize for b in books])
    elif (apiFormat == 'Atom'):
        return atomify([b.serialize for b in books])
    elif (apiFormat == 'RSS'):
        return rssify([b.serialize for b in books])
    else:
        return jsonify(Books=[b.serialize for b in books])


@home.route('/media/<path:filename>')
def media(filename):
    """For uploaded media files (principally book cover art, at
    present for this app), direct the browser appropriately.
    """
    dirname = os.path.dirname
    media_path = os.path.join(
        dirname(dirname(__file__)), app.config['MEDIA_FOLDER'])
    return send_from_directory(media_path, filename)
