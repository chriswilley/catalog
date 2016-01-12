from catalog import db
from catalog.models import Category

db.drop_all()
db.create_all()

categories = [
    "Art and Design",
    "Biography",
    "Business",
    "Crime",
    "Drama",
    "Fantasy",
    "Film and TV",
    "General Fiction",
    "History",
    "Literary Criticism",
    "Philosophy",
    "Poetry",
    "Religion",
    "Romance",
    "Science and Nature",
    "Science Fiction",
]

for i, x in enumerate(categories):
    new_category = Category(name=x)
    db.session.add(new_category)
    db.session.commit()
