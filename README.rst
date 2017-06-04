Tails: A Sidekick for Sanic apps
================================

A collection of utilities for Sanic (and/or Stellata and/or Webpack)
apps.

CLI
---

Suppose you have a project called ``foo``.

Run database migrations:

::

    tails foo migrate

Build webpack assets:

::

    tails foo build

Run a debug server that reloads on server + asset changes:

::

    tails foo server --watch --build

Run a production server:

::

    tails foo server --production --host=0.0.0.0 --port=9000

Run multiple projects at once:

::

    tails ~/foo/foo ~/bar/bar server --port=9001 --port=9002

Reset to a fresh database with no data:

::

    tails foo reset

Resource
--------

Return JSON or HTML pages:

::

    import foo
    import tails.resource

    @foo.app.route('/')
    async def index():
        return tails.resource.html(
            title='What a great page',
            external_css=['https://fonts.googleapis.com/icon?family=Material+Icons'],
            js=['/static/build/js/index.js'],
            css['/static/build/css/index.css']
        )

    @foo.app.route('/api')
    async def api():
        data = ...
        return tails.resource.json({
            'data': data
        })
