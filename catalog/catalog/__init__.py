import logging

from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

from flask_debugtoolbar import DebugToolbarExtension
from logging import Formatter, getLogger
from logging.handlers import RotatingFileHandler

app = Flask(__name__, instance_relative_config=True)

app.config.from_object('config')
app.config.from_pyfile('config.py')

db = SQLAlchemy(app)

toolbar = DebugToolbarExtension(app)

if not (app.debug):
    logfile = app.config['LOG_FILE']
    handler = RotatingFileHandler(logfile, maxBytes=10240, backupCount=10)
    handler.setLevel(logging.WARNING)
    handler.setFormatter(Formatter(
        '%(asctime)s %(levelname)s %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    loggers = [app.logger, getLogger('sqlalchemy')]
    for l in loggers:
        l.addHandler(handler)

from catalog.views.auth import auth
from catalog.views.home import home
from catalog.views.test import test

app.register_blueprint(auth)
app.register_blueprint(home)
app.register_blueprint(test)
