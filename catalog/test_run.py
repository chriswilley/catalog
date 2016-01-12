from catalog import app

app.testing = True

if (__name__) == '__main__':
    app.run(host='0.0.0.0', port=5000)
