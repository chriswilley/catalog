# Lending Library

This project sets up a lending library, so that a team can share books of interest with their teammates.


## Table of contents

* [Base setup](#base-setup)
* [App config](#app-config)
* [Instance config](#create-instance-config-file)
* [3rd Party Authentication](#3rd-party-authentication)
* [Facebook Authentication](#facebook-authentication)
* [Google+ Authentication](#google-authentication)
* [Google Books API](#google-books-api)
* [Run setup](#run-setup)
* [Book categories](#book-categories)
* [Running Lending Library](#running-lending-library)
* [Testing Lending Library](#testing-lending-library)
* [Debug toolbar](#debug-toolbar)
* [Creator](#creator)
* [Copyright and license](#copyright-and-license)


## Base setup

For starters, you need [Python](https://www.python.org/downloads/). The program was written for Python 2.7, so that's what you should download and install. You may already have Python, especially if you're on a Mac or Linux machine. To check, open a Terminal window (on a Mac, use the Spotlight search and type in "Terminal"; on a PC go to Start > Run and type in "cmd") and type "python" at the prompt. You should get something that looks like this (run on my Mac):

```
Python 2.7.10 (v2.7.10:15c95b7d81dc, May 23 2015, 09:33:12)
[GCC 4.2.1 (Apple Inc. build 5666) (dot 3)] on darwin
Type "help", "copyright", "credits" or "license" for more information.
>>>
```

Note the version number (2.7.10 in this case). If it starts with "3.", you should download version 2.7. If you have questions about any of this, check Python's [excellent online documentation](https://www.python.org/doc/).

You'll also need a database for Lending Library to connect to. There are a number of options, basically anything [SQLAlchemy can work with](http://docs.sqlalchemy.org/en/rel_1_0/core/engines.html#supported-databases). One note of caution: SQLite has a problem with decimal fields, and if you use that database you'll get a lot of warning messages in the logs about it. The application will work fine with SQLite, however.

There are a number of Python module dependencies for this project. To install them all, run the following:

```
pip install -r requirements.txt
```

Finally, you'll need [git](http://git-scm.com/download) so that you can clone this project.


## App config

Setting up Lending Library is pretty straightforward. First you need to create the database, and then [create an instance config file](#create-instance-config-file).

Here are the steps to create the database in PostgreSQL:

In a Terminal window, type:

```
psql
```

This will put you in the PostgreSQL shell environment. Your prompt will look like this: '=>', and you'll see a message similar to:

```
psql (9.3.9)
Type "help" for help.
```

Now you can execute SQL commands and do all kinds of other neat stuff. To setup the application database, type the following (note that we're using a DB name of 'catalog' here):

```
CREATE USER username WITH PASSWORD password;
CREATE DATABASE catalog WITH OWNER username;
```

For 'username' above, pick any username you like. For 'password', make sure to create a complex password made up of letters, numbers, symbols, all that jazz. When you're done, hit Ctrl-D to exit from the psql shell (or type \q and hit Enter). Make a note of the username, password and database name as you'll need them in the next section.


## Create instance config file

The app requires some configuration items that are deployment dependent. There is a starter file called instance_config_sample.py in the root folder, which has all the config parameters listed and waiting to be filled in. Enter the following in a Terminal window:

```
mkdir instance
cp instance_config_sample.py instance/config.py
```

The table below explains the config parameters.

Paramater | Description
--- | ---
SQLALCHEMY_DATABASE_URI | This is the database connection information Lending Library needs to attach to the database. For PostgreSQL, this would look like: "postgresql://db_owner:db_owner_password@hostname/db_name".
SQLALCHEMY_TRACK_MODIFICATIONS | This should be set to False due to an issue with Flask-SQLAlchemy and signals. [I don't recommend changing it to True.](http://stackoverflow.com/questions/33738467/sqlalchemy-who-needs-sqlalchemy-track-modifications/33790196#33790196)
SECRET_KEY | This is what Flask uses to sign cookies and handle sessions. This should be a long string of random characters to keep it safe. See below for more info.
DEBUG | If you're deploying this in a test or development environment, set this to True. Set it to False if you're deploying into a production environment.
DEBUG_TB_INTERCEPT_REDIRECTS | If you're using the Flask Debug Toolbar, I recommend that you set this to False, especially when running tests. If you set it to True you'll get an interstitial message from the DebugToolbar telling you it's redirecting, which you'll have to acknowledge. I only use it for specific debugging purposes.
USE_FACEBOOK_SIGNIN | If you want to enable authentication using the Facebook signin API, set this to True. See the next section regarding 3rd party authentication.
FACEBOOK_CONFIG | If using Facebook authentication, your app config goes here.
USE_GOOGLE_SIGNIN | If you want to enable authentication using the Google signin API, set this to True. See the next section regarding 3rd party authentication.
USE_GOOGLE_API | If you want to use the Google Books API, you'll need an API key and to set this to True.
GOOGLE_API_KEY | The Google API key you want to use to access the Google Books API.

For the SECRET_KEY setting, you should use a nice, long set of random characters as this key will be used for signing cookies and handling sessions. You can use a variety of online sources to generate the key, or use a function like the following:

```
python -c 'import random; import string; print "".join([random.SystemRandom().choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*(-_=+)") for i in range(100)])'
```

IMPORTANT NOTE: there is a config.py file in the Lending Library root folder. Don't remove or change that file (or overwrite it with the instance_config_sample.py file).


## 3rd Party Authentication

Lending Library supports signin using Facebook and Google+ APIs. As there is no built-in authentication mechanism, you must use one (or both) of these options in order for all of the features of the app to work. In order to use the 3rd party APIs for authentication, you'll need to establish the appropriate keys. Each authentication provider has a different process for obtaining these keys; see the next two sections for more details.


## Facebook Authentication

To use Facebook for authentication, you'll need a Facebook developer account. Then you can create a web app and generate API keys. See [Facebook's App Development docs](https://developers.facebook.com/docs/apps/register) for more info. Specifically, you'll need an app ID and app secret to plug into the instance config file's FACEBOOK_CONFIG parameter. It will look like this when you're done:

```
FACEBOOK_CONFIG = {"web":{"app_id":"[a long string of numbers]","app_secret":"[a longer string of numbers and letters]"}}
```


## Google Authentication

To use Google for authentication, you'll need a Google developer account. Then you will need to create a web project and generate an OAuth2.0 Client ID, which you can then download as a JSON file (see below). See [Google's API docs](https://developers.google.com/identity/sign-in/web/devconsole-project) for more info (the documentation page linked here says you don't need to create Authorized Redirect URIs, but you do; see below).

Once you've established the credentials for a new project in the Google Developer's console, you need to create a config_secrets.json file in the 'instance/' folder along with the config.py file. Here's what your client_secrets.json file will look like when you're done:

```
{
    "web":{
        "client_id":"[a long string of letters and numbers].apps.googleusercontent.com",
        "auth_uri":"https://accounts.google.com/o/oauth2/auth",
        "token_uri":"https://accounts.google.com/o/oauth2/token",
        "auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs",
        "client_secret":"[another string of letters and numbers]",
        "redirect_uris":[
            # see below
        ],
        "javascript_origins":[
            # also see below
        ]
    }
}
```

The 'redirect_uris' parameter must contain at least two items: the root of the application and the location of the 'oauth2callback' view. On a development box, this will probably look like this:

```
"redirect_uris": [
    "http://localhost:5000/",
    "http://localhost:5000/oauth2callback"
]
```

The 'javascript origins' parameter should contain just the root of your application:

```
"javascript_origins": [
    "http://localhost:5000"
]
```

These two parameters are specified when you create the app in the Google Developer's console in the Authorized Redirect URIs setting. When you deploy this app in production, you'll need new redirect_uris and javascript_origins to match the hostname you're deploying to.

For more info on the client_secrets.json file, [see the documentation](https://developers.google.com/api-client-library/python/guide/aaa_client_secrets).


## Google Books API

If you want to allow users to use the Google Books API to pull in book cover art and other metadata, set USE_GOOGLE_API in the instance config file equal to True and provide the API key in GOOGLE_API_KEY. You can generate the API key in the same Developer's Console project as the Google Sign-In API above. [See the docs for more info](https://developers.google.com/console/help/new/#usingkeys).


## Run Setup

After the above steps are done, type the following in a Terminal window from the main catalog folder:

```
python setup.py
```

If all the config items are correct, the database will be set up and some initial data will be inserted into tables. With that, the application is ready to go!


## Book categories

The category list for books is in the setup.py file. If you want a different set of categories, you can change the list prior to running setup.


## Running Lending Library

If you're in a development or test environment, type the following in a Terminal window from the catalog root folder:

```
python run.py
```

If you're in a production environment, you'll need to set up a proper web server or use a hosting provider that can handle Flask applications such as Heroku or dotCloud. There are lots of online resources that explain how to do both of those things; check out Flask's [documentation](http://flask.pocoo.org/docs/0.10/deploying/#deployment) for lots of options.


## Testing Lending Library

There are a number of unit tests in test.py. In order to test the app, a test server must be running to respond to some mock HTTP requests. A test server is provided; just run:

```
python test_run.py
```

Once you've done that, in another Terminal window you can run:

```
python test.py
```

from the main "catalog" folder.


## Debug Toolbar

Lending Library also has Flask-DebugToolbar installed, which will only be visible if you have "DEBUG = True" in your instance config (i.e.: on a test or development server). The utility is handy when troubleshooting problems. If you want to disable it, add an instance config parameter as follows:

```
DEBUG_TB_ENABLED = False
```

Other configuration info can be found in the [documentation](http://flask-debugtoolbar.readthedocs.org/en/latest/).


## Creator

This program was built by me, Chris Willey, as part of the Udacity Nanodegree program for [Full Stack Developer](https://www.udacity.com/course/full-stack-web-developer-nanodegree--nd004).


## Copyright and License

Code and documentation copyright 2015 Christopher Willey. Code released under the MIT license.