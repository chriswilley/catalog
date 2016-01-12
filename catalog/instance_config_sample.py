# SQLAlchemy config
SQLALCHEMY_DATABASE_URI = ""  # put SQLAlchemy database connection info here
SQLALCHEMY_TRACK_MODIFICATIONS = False  # don't change this setting

# app secret key
SECRET_KEY = ""  # put your app secret key here to protect sessions and cookies safe

# in debug mode? don't do this in production
DEBUG = True  # set to False in production

# if using the Flask debug toolbar, don't intercept redirects; it's a pain
DEBUG_TB_INTERCEPT_REDIRECTS = False  # recommended setting, especially for testing

# 3rd party sign-in config
USE_FACEBOOK_SIGNIN = False  # set to True if you have Facebook sign-in enabled
FACEBOOK_CONFIG = ''  # place your Facebook signin API config here; see README
USE_GOOGLE_SIGNIN = False  # set to True if you have Google sign-in enables

# Google Books API config
USE_GOOGLE_API = False  # set to True if you plan to use the Google Books API functionality
GOOGLE_API_KEY = ''  # if above is True, API key goes here
