import json
import os
import re
import time

from datetime import datetime as dt
from flask import g, make_response, url_for, session as login_session, redirect
from functools import wraps
from sqlalchemy.orm.exc import NoResultFound
from werkzeug import secure_filename
from xml.dom.minidom import Document as xmldoc

from . import app
from .models import Book, Category


def login_required(_next=None):
    """Ensure user is logged in before proceeding with a function, or else
    redirect to `auth.loginRequired`. This is used as a decorator.
    """
    def login_required_wrapper(func):
        @wraps(func)
        def decorated_view(*args, **kwargs):
            # provide a 'next' argument to redirect the user after login
            if not (_next):
                go_next = url_for('home.showBooks')
            elif ('book_id' in kwargs):
                go_next = url_for(_next, book_id=kwargs['book_id'])
            else:
                go_next = url_for(_next)

            if ('username' not in login_session):
                # user not authenticated, redirect to login required message
                return redirect(
                    url_for('auth.loginRequired', next=go_next))
            else:
                return func(*args, **kwargs)
        return decorated_view
    return login_required_wrapper


def book_exists(func):
    """Ensure a book exists before attempting to do something with
    it in a function (like borrowing it, or reviewing it, etc.).
    This is used as a decorator.
    """
    @wraps(func)
    def decorated_view(*args, **kwargs):
        try:
            # if book with book_id doesn't exist, redirect
            book = Book.query.filter_by(id=kwargs['book_id']).one()

            # return Book object so we don't have to do another SQL query
            # back in the originating function
            kwargs['book'] = book

            return func(*args, **kwargs)
        except NoResultFound:
            return redirect(url_for('home.showBooks'))

    return decorated_view


def report_json_error(msg, code=401):
    """During authentication, errors are reported back to the app
    using this function.
    """
    response = make_response(json.dumps(msg), code)
    response.headers['Content-Type'] = 'application/json'
    return response


def filter_books(_filter, thisCategory=None):
    """Return a list of books by a user-specified filter. Filtering a
    list of books is done by more than one function, so putting the code
    here saves some repetition.
    """
    if (_filter == 'mybooks'):
        # books lent by the user
        books = Book.query.filter_by(lender=g.user).all()
    elif (_filter == 'favorites'):
        # books marked by user as favorites
        books = Book.query.filter(Book.favorite.contains(g.user)).all()
    elif (_filter == 'category'):
        # books of a certain genre/category
        cat = Category.query.filter_by(name=thisCategory).one()
        books = Book.query.filter(Book.category.contains(cat)).all()
    elif (_filter == 'all'):
        # all books
        books = Book.query.all()
    else:
        # most recent 8 books (why 8? it's two rows of four in
        # the template at full width)
        books = Book.query.order_by(Book.date_added.desc()).limit(8)

    return books


def set_image_name(filename):
    """When uploading a picture to attach to an object (like cover
    art for a Book), there needs to be a way to ensure unique file
    names. Otherwise, you might overwrite another book's cover art
    by mistake. This function appends the current date and time as
    a string to the beginning of the uploaded file name along with
    an underscore ("_"). time.mktime returns the number of seconds
    between January 1, 1970 and the date/time you specify. Makes
    user of Werkzeug's excellent secure_filename function to
    prevent malicious filenames (like ones using forward slashes).
    See: https://docs.python.org/2/library/time.html
    Also: http://werkzeug.pocoo.org/docs/0.11/utils/
    """
    epoch = int(time.mktime(time.localtime()))
    return str(epoch) + '_' + secure_filename(filename)


def save_uploaded_image(image):
    """Save an uploaded file to the appropriate folder (set in
    config.py). Return the filename so it can be saved to the DB.
    """
    upload_path = os.path.join(
        os.path.dirname(__file__), app.config['UPLOAD_FOLDER'])
    filename = set_image_name(image.filename)
    image.save(upload_path + '/' + filename)
    return filename


def xmlify(model, q):
    """Serialize a Python dict as generic XML using xml.dom.minidom.
    See: https://docs.python.org/2/library/xml.html
    """
    doc = xmldoc()
    _xml = doc.appendChild(doc.createElement(model + 's'))
    for obj in q:
        node = _xml.appendChild(doc.createElement(model))

        for key, value in obj.iteritems():
            nodesub = node.appendChild(doc.createElement(key))
            nodesub.appendChild(doc.createTextNode(unicode(value)))

    resp = app.response_class(
        doc.toprettyxml(indent='    ', encoding='utf-8'),
        mimetype='application/xml'
    )

    return resp


def atomify(q):
    """Serialize a Python dict as XML using xml.dom.minidom,
    this time constructing the document according to the Atom
    Syndication Format. The resulting document can be used by
    feed readers like Google's Feedburner.
    See: https://tools.ietf.org/html/rfc4287
    """
    doc = xmldoc()
    _xml = doc.appendChild(doc.createElement('feed'))
    _xml.setAttribute('xmlns', 'http://www.w3.org/2005/Atom')
    title = _xml.appendChild(doc.createElement('title'))
    title.appendChild(doc.createTextNode('Book List from Lending Library'))
    link = _xml.appendChild(doc.createElement('link'))
    link.setAttribute('href', url_for('home.booksAPI', _external=True))
    link.setAttribute('rel', 'self')
    feed_id = _xml.appendChild(doc.createElement('id'))
    feed_id.appendChild(
        doc.createTextNode(url_for('home.catalogHome', _external=True)))
    update_date = dt.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    updated = _xml.appendChild(doc.createElement('updated'))
    updated.appendChild(doc.createTextNode(update_date))

    for obj in q:
        entry = _xml.appendChild(doc.createElement('entry'))

        entry_title = entry.appendChild(doc.createElement('title'))
        entry_title.appendChild(doc.createTextNode(obj['title']))

        eLink = url_for('home.bookInfo', book_id=obj['id'], _external=True)
        entry_link = entry.appendChild(doc.createElement('link'))
        entry_link.setAttribute('href', eLink)

        host = re.search(r'//(.+?)/(.+)/', eLink)
        entry_tag = 'tag:' + host.group(1) + ','
        entry_tag += obj['date_added'].strftime('%Y-%m-%d')
        entry_tag += ':/' + host.group(2)
        entry_id = entry.appendChild(doc.createElement('id'))
        entry_id.appendChild(doc.createTextNode(entry_tag))

        entry_date = obj['date_added'].strftime('%Y-%m-%dT%H:%M:%SZ')
        entry_updated = entry.appendChild(doc.createElement('updated'))
        entry_updated.appendChild(doc.createTextNode(entry_date))

        entry_summary = entry.appendChild(doc.createElement('summary'))
        entry_summary.appendChild(doc.createTextNode(obj['synopsis']))

        author = entry.appendChild(doc.createElement('author'))
        author_name = author.appendChild(doc.createElement('name'))
        author_name.appendChild(doc.createTextNode(obj['author']))

        year_pub = entry.appendChild(doc.createElement('yearpublished'))
        year_pub.appendChild(doc.createTextNode(str(obj['year_published'])))

        picture = entry.appendChild(doc.createElement('picture'))
        picture.appendChild(doc.createTextNode(obj['picture']))

        avail = entry.appendChild(doc.createElement('isavailable'))
        avail.appendChild(doc.createTextNode(str(obj['is_available'])))

        if (obj['due_date'] is not None):
            ts = time.strptime(obj['due_date'], '%m/%d/%Y')
            due_date = dt.fromtimestamp(time.mktime(ts))
            entry_due_date = due_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            due_date = entry.appendChild(doc.createElement('duedate'))
            due_date.appendChild(doc.createTextNode(entry_due_date))

        lender = entry.appendChild(doc.createElement('lender'))
        lender_email = lender.appendChild(doc.createElement('email'))
        lender_email.appendChild(doc.createTextNode(obj['lender']))

        if (obj['borrower'] is not None):
            borrower = entry.appendChild(doc.createElement('borrower'))
            borrower_name = borrower.appendChild(doc.createElement('name'))
            borrower_name.appendChild(
                doc.createTextNode(obj['borrower']['name']))
            borrower_email = borrower.appendChild(doc.createElement('email'))
            borrower_email.appendChild(
                doc.createTextNode(obj['borrower']['email']))

    resp = app.response_class(
        doc.toprettyxml(indent='    ', encoding='utf-8'),
        mimetype='application/atom+xml'
    )

    return resp


def rssify(q):
    """Serialize a Python dict as XML using xml.dom.minidom,
    this time constructing the document according to the RSS
    (Rich Site Summary) format. The resulting document can be
    used by feed readers like Google's Feedburner.
    See: http://www.rssboard.org/rss-specification
    """
    doc = xmldoc()
    _rss = doc.appendChild(doc.createElement('rss'))
    _rss.setAttribute('version', '2.0')
    channel = _rss.appendChild(doc.createElement('channel'))
    title = channel.appendChild(doc.createElement('title'))
    title.appendChild(doc.createTextNode('Book List from Lending Library'))
    desc = channel.appendChild(doc.createElement('description'))
    desc.appendChild(
        doc.createTextNode('A list of books from the Lending Library.'))
    link = channel.appendChild(doc.createElement('link'))
    link.appendChild(
        doc.createTextNode(url_for('home.booksAPI', _external=True)))
    date_format = '%a, %d %b %Y %H:%M:%S +0000'
    update_date = dt.utcnow().strftime(date_format)
    pub_date = channel.appendChild(doc.createElement('pubDate'))
    pub_date.appendChild(doc.createTextNode(update_date))

    for obj in q:
        item = channel.appendChild(doc.createElement('item'))

        item_title = item.appendChild(doc.createElement('title'))
        item_title.appendChild(doc.createTextNode(obj['title']))

        eLink = url_for('home.bookInfo', book_id=obj['id'], _external=True)
        item_link = item.appendChild(doc.createElement('link'))
        item_link.appendChild(doc.createTextNode(eLink))

        item_date = obj['date_added'].strftime(date_format)
        item_updated = item.appendChild(doc.createElement('pubDate'))
        item_updated.appendChild(doc.createTextNode(item_date))

        item_summary = item.appendChild(doc.createElement('description'))
        item_summary.appendChild(doc.createTextNode(obj['synopsis']))

        author = item.appendChild(doc.createElement('author'))
        author.appendChild(doc.createTextNode(obj['author']))

        year_pub = item.appendChild(doc.createElement('yearpublished'))
        year_pub.appendChild(doc.createTextNode(str(obj['year_published'])))

        picture = item.appendChild(doc.createElement('picture'))
        picture.appendChild(doc.createTextNode(obj['picture']))

        avail = item.appendChild(doc.createElement('isavailable'))
        avail.appendChild(doc.createTextNode(str(obj['is_available'])))

        if (obj['due_date'] is not None):
            ts = time.strptime(obj['due_date'], '%m/%d/%Y')
            due_date = dt.fromtimestamp(time.mktime(ts))
            item_due_date = due_date.strftime(date_format)
            due_date = item.appendChild(doc.createElement('duedate'))
            due_date.appendChild(doc.createTextNode(item_due_date))

        lender = item.appendChild(doc.createElement('lender'))
        lender.appendChild(doc.createTextNode(obj['lender']))

        if (obj['borrower'] is not None):
            borrower_str = obj['borrower']['email'] + ' ('
            borrower_str += obj['borrower']['name'] + ')'
            borrower = item.appendChild(doc.createElement('borrower'))
            borrower.appendChild(doc.createTextNode(borrower_str))

    resp = app.response_class(
        doc.toprettyxml(indent='    ', encoding='utf-8'),
        mimetype='application/rss+xml'
    )

    return resp


@app.template_filter('pluralize')
def pluralize_filter(value, arg='s'):
    """
    Borrowed from Django (django.template.defaultfilters). This filter
    takes a string and adds characters in order to put it in plural
    form (e.g.: 'book' becomes 'books'). Sometimes just adding an 's'
    isn't sufficient in the English language (e.g.: 'french fry'
    becomes 'french fries'), so the filter allows the user to specify
    the characters to add.

    To use this in a template (for example, to say '4 reviews' or
    '1 review' for a book):

        review{{ book.rating|length|pluralize }}
    """
    if ',' not in arg:
        arg = ',' + arg
    bits = arg.split(',')
    if len(bits) > 2:
        return ''
    singular_suffix, plural_suffix = bits[:2]

    try:
        if float(value) != 1:
            return plural_suffix
    except ValueError:  # Invalid string that's not a number.
        pass
    except TypeError:  # Value isn't a string or a number; maybe it's a list?
        try:
            if len(value) != 1:
                return plural_suffix
        except TypeError:  # len() of unsized object.
            pass
    return singular_suffix
