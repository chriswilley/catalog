import json
import os

from catalog import app


def delete_test_file(filename):
    """Delete a named file used for testing purposes.
    """
    file_path = os.path.join(
        os.path.dirname(__file__), filename)
    os.remove(file_path)
    return


def get_google_client_id():
    """Since we have to do this a number of times while testing the Google
    authentication process, save ourselves some typing by putting the
    code in a callable function. Facebook API details are in config.py,
    so we can just use app.config['FACEBOOK_CONFIG'] for that.
    """
    client_id = json.loads(
        open('instance/client_secrets.json', 'r').read())['web']['client_id']

    return client_id


def save_google_secrets_test_files():
    """Generate JSON files for testing the Google authentication
    process. Note that all we're doing is changing the token_uri
    parameter.
    """
    with open('instance/client_secrets.json', 'r') as f:
        cs = json.loads(f.read())

    cs['web']['token_uri'] = 'http://localhost:5000/test/get_access_token/'

    with open('instance/client_secrets_test.json', 'w') as f2:
        f2.write(json.dumps(cs))

    url = 'http://localhost:5000/test/get_wrong_access_token/'
    cs['web']['token_uri'] = url

    with open('instance/client_secrets_bogus_test.json', 'w') as f3:
        f3.write(json.dumps(cs))

    return
