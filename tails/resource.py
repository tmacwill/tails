import sanic.response
import stellata.model

def bad_request():
    return sanic.response.text('', status=400)

def forbidden():
    return sanic.response.text('', status=403)

def json(data):
    return sanic.response.HTTPResponse(stellata.model.serialize(data), content_type='application/json')

def ok(data=None):
    if data is None:
        data = {}

    data['ok'] = True
    return json(data)

def redirect(url):
    return sanic.response.redirect(url)

def unauthorized():
    return sanic.response.text('', status=401)
