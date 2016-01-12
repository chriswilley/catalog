from flask import make_response, redirect, request, url_for, jsonify
from functools import wraps
from oauth2client._helpers import _urlsafe_b64encode

from . import test
from .. import app


def check_testing(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not (app.testing):
            # redirect the user if we're not in testing mode
            return redirect(url_for('home.catalogHome'))
        else:
            return func(*args, **kwargs)
    return decorated_view


@test.route('/test/get_access_token/', methods=['POST'])
@check_testing
def getAccessToken():
    """This view simulates a Google sign-in API response to a
    request for a redirect URI. Returns a JSON response.
    """
    id_token = '{"sub": "110169484474386276334", "email": "admin@catalog.com"}'
    # Google Base64-encodes the id_token, so we must also for the
    # test to work
    id_token_encoded = _urlsafe_b64encode(id_token)

    # note the fake access_token; in this case, the token is not
    # validated so it can be whatever we want
    # the id_token sent to Google must be a string delimited by
    # '.'; Google looks for three segments (using split()) and takes
    # the middle one, hence the configuration shown here
    token_response = {
        'access_token': 'splunge',
        'id_token': 'app.' + id_token_encoded + '.catalog'
    }
    return jsonify(token_response)


@test.route('/test/get_wrong_access_token/', methods=['POST'])
@check_testing
def getWrongAccessToken():
    """This view simulates a Google sign-in API response to a
    request for a redirect URI. Returns a JSON response. In this
    case, we're sending a response missing it's access_token
    parameter in order to test that scenario.
    """
    id_token = '{"sub": "110169484474386276334", "email": "admin@catalog.com"}'
    id_token_encoded = _urlsafe_b64encode(id_token)

    # no access token this time
    token_response = {
        'id_token': 'app.' + id_token_encoded + '.catalog'
    }
    return jsonify(token_response)


@test.route('/test/check_token')
@check_testing
def checkToken():
    """This view simulates a Google sign-in API response to a
    request to verify a given token. Returns a JSON response
    containing the expected user's ID and the app's client_id.
    """
    # the 'issued_to' parameter is the client_id of the app
    token_response = {
        'user_id': request.args.get('id'),
        'issued_to': request.args.get('issued')
    }
    return jsonify(token_response)


@test.route('/test/userinfo/')
@check_testing
def userInfo():
    """This view simulates a Google sign-in API response to a
    request for a user's info. Returns a JSON response
    containing the user's name, email and picture URL.
    """
    userinfo_response = {
        'name': 'admin',
        'email': 'admin@catalog.com',
        'picture': 'http://catalog.com/user.png'
    }
    return jsonify(userinfo_response)


@test.route('/test/revoke_token/<access_token>/')
@check_testing
def revokeToken(access_token):
    """This view simulates a Google sign-in API response to a
    request to revoke a granted token. Returns a JSON response.
    This is part of the logout process.
    """
    if (access_token == 'goodtoken'):
        response = make_response('Yay!', 200)
    else:
        response = make_response('D\'oh!', 401)

    return response


@test.route('/test/fbget_token/')
@check_testing
def fbGetToken():
    """This view simulates a Facebook sign-in API response to a
    request to receive an authorization token. Returns an HTTP
    response object.
    """
    token_response = make_response(
        'token=hereisyourtoken&extrastuff=stuff', 200)

    return token_response


@test.route('/test/fbget_profile/')
@check_testing
def fbGetProfile():
    """This view simulates a Facebook sign-in API response to a
    request for a user's info. Returns a JSON response containing
    the user's name, Facebook id and email.
    """
    userinfo_response = {
        'name': 'admin',
        'email': 'admin@catalog.com',
        'id': 'admin'
    }
    return jsonify(userinfo_response)


@test.route('/test/fbget_picture/')
@check_testing
def fbGetPicture():
    """This view simulates a Facebook sign-in API response to a
    request for a user's picture. Returns a JSON response. No idea
    why this is a separate API call from getting user info.
    """
    userinfo_response = {
        'data': {
            'url': 'http://catalog.com/user.png'
        }
    }
    return jsonify(userinfo_response)
