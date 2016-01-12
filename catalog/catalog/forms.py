from datetime import datetime as dt
from flask_wtf import Form
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    DecimalField,
    IntegerField,
    StringField,
    TextAreaField,
)
from wtforms.validators import DataRequired, NumberRange, Optional
from wtforms.widgets import HiddenInput
from wtforms.ext.sqlalchemy.fields import QuerySelectMultipleField

from . import app
from .models import Category


def get_categories():
    categories = Category.query.all()
    return categories


class BookForm(Form):
    if (app.config['USE_GOOGLE_API']):
        picture_desc = 'If you leave this blank, the cover image will be '
        picture_desc += 'pulled from the Google Books API'
    else:
        picture_desc = ''

    title = StringField(validators=[DataRequired('Title is required.'), ])
    author = StringField(validators=[DataRequired('Author is required.'), ])
    year_published = IntegerField(
        validators=[Optional(), NumberRange(min=1, max=dt.today().year), ])
    category = QuerySelectMultipleField(
        'Genre(s)',
        query_factory=get_categories,
        validators=[DataRequired('Please choose a genre'), ]
    )
    picture = FileField('Book Cover', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Please only upload image files')
    ], description=picture_desc)
    synopsis = TextAreaField()


class SearchForm(Form):
    searchterm = StringField('', validators=[DataRequired(), ])


class ReviewForm(Form):
    rating = DecimalField(
        widget=HiddenInput(),
        places=1,
        validators=[NumberRange(min=0.0, max=5.0), ])
    review = TextAreaField()
