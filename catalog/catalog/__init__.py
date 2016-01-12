from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

from flask_debugtoolbar import DebugToolbarExtension

app = Flask(__name__, instance_relative_config=True)

app.config.from_object('config')
app.config.from_pyfile('config.py')

db = SQLAlchemy(app)

toolbar = DebugToolbarExtension(app)

from catalog.views.auth import auth
from catalog.views.home import home
from catalog.views.test import test

app.register_blueprint(auth)
app.register_blueprint(home)
app.register_blueprint(test)
