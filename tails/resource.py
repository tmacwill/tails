import json as j
import sanic.response
import stellata.model

def _css_tag(path):
    if not path:
        return ''

    return '<link rel="stylesheet" type="text/css" href="%s" />' % path

def _js_tag(path):
    if not path:
        return ''

    return '<script type="text/javascript" src="%s"></script>' % path

def bad_request():
    return sanic.response.text('', status=400)

def forbidden():
    return sanic.response.text('', status=403)

def html(body='', head='', title='', css=None, js=None, js_data=None, external_css=None, external_js=None):
    css = css or []
    js = js or []
    js_data = js_data or {}
    external_css = external_css or []
    external_js = external_js or []

    if not isinstance(css, list):
        css = [css]

    if not isinstance(js, list):
        js = [js]

    if not isinstance(external_css, list):
        external_css = [external_css]

    if not isinstance(external_js, list):
        external_js = [external_js]

    return sanic.response.html('''<!doctype html>
<html>
  <head>
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
    <title>%s</title>
    <script type="text/javascript">window.__data__ = %s;</script>
    %s
    %s
    %s
  </head>
  <body>
    <div id="container">%s</div>
    %s
    %s
  </body>
</html>
    ''' % (
        title,
        j.dumps(js_data),
        ''.join([_css_tag(e) for e in external_css]),
        ''.join([_css_tag(e) for e in css]),
        head,
        body,
        ''.join([_js_tag(e) for e in external_js]),
        ''.join([_js_tag(e) for e in js]),
    ))

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
