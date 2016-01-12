import httplib2
import json
import random
import requests
import string

from flask import (
    flash,
    redirect,
    render_template,
    request,
    session as login_session,
    url_for
)
from oauth2client.client import flow_from_clientsecrets, FlowExchangeError

from . import auth
from .. import app, db
from ..utils import report_json_error
from ..models import User

CLIENT_ID = json.loads(
    open('instance/client_secrets.json', 'r').read())['web']['client_id']


@auth.route('/login/')
def showLogin():
    """Present the login options to the user (currently Google+ and
    Facebook). Also set the STATE variable to help prevent cross site
    forgeries (sort of a poor man's CSRF). The STATE variable set here
    as a session variable will be checked again when the 3rd-party
    authentication process begins.
    """
    state = ''.join(random.choice(
        string.ascii_uppercase + string.digits) for x in xrange(32))
    login_session['state'] = state
    _next = ''
    if (request.args.get('next')):
        # provide a way to direct the user after authenticating
        _next = request.args.get('next')
    return render_template('login.html', STATE=state, next=_next)


@auth.route('/login_required/')
def loginRequired():
    """If the user is not authenticated, certain features are locked
    (adding a book, checking one out, etc.). Under these circumstances,
    inform the user before redirecting to the signin process. That's
    what this template is for. Nicer UX, no?
    """
    return render_template('login_required.html')


@auth.route('/oauth2callback')
def gconnect():
    """If we're using Google+ for authentication, start here. This function
    is called when users click the `Sign in using Google` button on the
    login.html page.
    """
    if (request.args.get('next')):
        login_session['next'] = request.args.get('next')

    if (app.testing):
        # if we're testing the app, use mocked server responses
        # instead of the real thing
        secret_file = request.args.get('secret')
        access_token_uri = 'http://localhost:5000/test'
        access_token_uri += '/check_token?id=' + request.args.get('id')
        access_token_uri += '&issued=' + request.args.get('issued')
        access_token_uri += '&access_token'
        userinfo_url = 'http://localhost:5000/test/userinfo/'
    else:
        secret_file = 'instance/client_secrets.json'
        access_token_uri = 'https://www.googleapis.com/oauth2/v1'
        access_token_uri += '/tokeninfo?access_token'
        userinfo_url = 'https://www.googleapis.com/oauth2/v1/userinfo'

    # Step 1 in authenticating through Google is to call the
    # `flow_from_clientsecrets function in oauth2client.client.
    # This returns a `Flow` object, which is documented here:
    # https://developers.google.com/api-client-library/python/guide/aaa_oauth
    oauth_flow = flow_from_clientsecrets(
        secret_file,
        scope='https://www.googleapis.com/auth/plus.profile.emails.read',
        redirect_uri=url_for('auth.gconnect', _external=True)
    )
    oauth_flow.params['include_granted_scopes'] = 'true'
    if ('code' not in request.args):
        # on the first pass, we just want the authorization URL
        if (request.args.get('state') != login_session['state']):
            # remember the poor man's CSRF? Here's where we check it
            return report_json_error('Invalid state parameter')
        else:
            auth_uri = oauth_flow.step1_get_authorize_url()
            return redirect(auth_uri)
    else:
        # after the user has authorized the app, we'll have a code we can
        # use to get whatever information we're entitled to (such as
        # the user's name, email and profile picture)
        try:
            credentials = oauth_flow.step2_exchange(request.args.get('code'))
        except FlowExchangeError as e:
            # something squirrely about the auth code? flag it here
            return report_json_error(
                'Failed to upgrade the authorization code: ' + str(e))

    access_token = credentials.access_token
    access_token_uri += '=%s' % access_token

    # here we visit the Google OAuth url responsible for validating that
    # this app is what it claims to be, and verifying what info it's
    # entitled to have
    h = httplib2.Http()
    resp = h.request(access_token_uri, 'GET')[1]
    result = json.loads(resp)

    if (result.get('error') is not None):
        # if Google complains, report the error and abort
        return report_json_error(result.get('error'), 500)
    gplus_id = credentials.id_token['sub']

    if (result['user_id'] != gplus_id):
        # if the user id we're expecting isn't the one we receive, abort
        # and report the problem
        return report_json_error(
            'Token\'s user ID doesn\'t match given user ID.')

    if (result['issued_to'] != CLIENT_ID):
        # similarly, if the app's client_id doesn't match, abort
        # and report the error
        return report_json_error('Token\'s client ID doesn\'t match app\'s.')

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if (stored_credentials is not None and gplus_id == stored_gplus_id):
        # if we went through all of this for nothing since the user
        # is already authenticated, move on with our lives
        return report_json_error('Current user is already connected', 200)

    login_session['provider'] = 'google'
    login_session['credentials'] = credentials.to_json()
    login_session['gplus_id'] = gplus_id

    # now we know we're good to go, so grab the user profile info
    # from the appropriate Google URL
    params = {'access_token': access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)
    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    if ('email' not in data):
        login_session['email'] = credentials.id_token['email']
    else:
        login_session['email'] = data['email']

    user_id = getUserID(login_session['email'])
    if not (user_id):
        # if this is a new user (from the LendingLibrary app perspective)
        # create the User object corresponding to the Google+ user
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    flash('You are now logged in as %s' % login_session['username'])
    return redirect(url_for('home.showBooks'))


def gdisconnect():
    """When Google+ users logout from the app, revoke the authentication
    token in addition to logging out.
    """
    if ('credentials' in login_session):
        credentials = json.loads(login_session.get('credentials'))
    else:
        return report_json_error('Current user is not connected.')

    access_token = credentials['access_token']
    if (app.testing):
        # again if we're testing, use mocked server responses
        url = 'http://localhost:5000/test/revoke_token/%s/' % access_token
    else:
        url = 'https://accounts.google.com/o/oauth2'
        url += '/revoke?token=%s' % access_token

    # send the token revoke signal
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]

    # delete the user session variables
    del login_session['gplus_id']
    del login_session['credentials']

    if (result['status'] == '200'):
        # if Google gives the thumbs-up, report success
        return report_json_error('Successfully disconnected.', 200)
    else:
        # otherwise let the user know the token wasn't revoked for
        # some reason; user is still logged out from the perspective
        # of the app
        return report_json_error('Failed to revoke token for given user.', 400)


@auth.route('/fbconnect', methods=['POST'])
def fbconnect():
    """Here's the Facebook authentication routine. This is somewhat more
    straightforward than Google+, but more or less the same process. The
    main difference here is that this function is called after the user has
    authorized the app. Hence, we don't have a redirect URI to handle.
    """
    if (request.args.get('state') != login_session['state']):
        # remember the poor man's CSRF? Here's where we check it
        return report_json_error('Invalid state parameter.')

    # the access token is already present since the user has
    # authorized the app; this will be passed back to Facebook
    # in order to get the profile data
    access_token = request.data

    fb_config = app.config['FACEBOOK_CONFIG']
    app_id = json.loads(fb_config)['web']['app_id']
    app_secret = json.loads(fb_config)['web']['app_secret']
    if (app.testing):
        # if we're testing, use mocked server responses
        token_url = 'http://localhost:5000/test/fbget_token/'
        profile_url = 'http://localhost:5000/test/fbget_profile/?'
        picture_url = 'http://localhost:5000/test/fbget_picture/'
    else:
        token_url = 'https://graph.facebook.com/oauth/access_token'
        profile_url = 'https://graph.facebook.com/v2.5/me?'
        picture_url = 'https://graph.facebook.com/v2.5/me/picture'

    token_url += '?grant_type=fb_exchange_token&client_id=%s' % app_id
    token_url += '&client_secret=%s' % app_secret
    token_url += '&fb_exchange_token=%s' % access_token

    # pull down the user profile info, except for the user's photo
    h = httplib2.Http()
    result = h.request(token_url, 'GET')[1]

    token = result.split('&')[0]

    profile_url += '%s&fields=name,id,email' % token
    h = httplib2.Http()
    result = h.request(profile_url, 'GET')[1]
    data = json.loads(result)
    login_session['provider'] = 'facebook'
    login_session['username'] = data['name']
    login_session['email'] = data['email']
    login_session['facebook_id'] = data['id']
    login_session['access_token'] = access_token

    # not sure why, but there's a separate URL for pulling down
    # the user profile photo; here's where we call that
    picture_url += '?%s' % token
    picture_url += '&redirect=0&height=200&width=200'
    h = httplib2.Http()
    result = h.request(picture_url, 'GET')[1]
    data = json.loads(result)

    login_session['picture'] = data['data']['url']

    user_id = getUserID(login_session['email'])
    if not (user_id):
        # if this is a new user (from the LendingLibrary app perspective)
        # create the User object corresponding to the Facebook user
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    flash('You are now logged in as %s' % login_session['username'])
    return 'Success'


@auth.route('/disconnect/')
def disconnect():
    """When a user clicks `Logout`, this is the function called. Mostly
    the same functionality independent of OAuth provider, but a couple
    of differences with regard to session variables set/removed.
    """
    if ('provider' in login_session):
        if (login_session['provider'] == 'google'):
            gdisconnect()

        if (login_session['provider'] == 'facebook'):
            del login_session['facebook_id']

        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        flash('You have been successfully logged out.')
        return redirect(url_for('home.catalogHome'))
    else:
        flash('You were not logged in to begin with!')
        return redirect(url_for('home.catalogHome'))


def createUser(login_session):
    """Create a new User object if it doesn't already exist when a user
    authenticates to the app.
    """
    newUser = User(
        name=login_session['username'],
        email=login_session['email'],
        picture=login_session['picture']
    )
    db.session.add(newUser)
    db.session.commit()
    user = User.query.filter_by(
        email=login_session['email']).one()
    return user.id


def getUserID(email):
    """Given a user's email address, return the user's ID."""
    try:
        user = User.query.filter_by(email=email).one()
        return user.id
    except:
        return None
