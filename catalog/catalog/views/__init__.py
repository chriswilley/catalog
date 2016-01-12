import json

from flask import Blueprint, g, session as login_session

from .. import app
from ..models import User

auth = Blueprint('auth', __name__)
home = Blueprint('home', __name__)
test = Blueprint('test', __name__)


@home.before_app_request
@auth.before_app_request
def pre_request():
    current_user = None
    if ('email' in login_session):
        try:
            current_user = User.query.filter_by(
                email=login_session['email']).one()
        except:
            pass
    g.user = current_user
    if (app.config['USE_GOOGLE_SIGNIN'] == True):
        g.gclient_id = json.loads(open(
            'instance/client_secrets.json', 'r').read())['web']['client_id']
    else:
        g.gclient_id = None

    if (app.config['USE_FACEBOOK_SIGNIN'] == True):
        g.fb_appid = json.loads(app.config['FACEBOOK_CONFIG'])['web']['app_id']
    else:
        g.fb_appid = None
