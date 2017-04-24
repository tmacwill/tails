# Tails

A collection of utilities for Sanic (and/or Stellata and/or Webpack) apps.

## Guide

Suppose you have a project called `foo`.

Run database migrations:

    tails foo migrate

Build webpack assets:

    tails foo build

Run a debug server that reloads on server + asset changes:

    tails foo server --watch --build

Run a production server:

    tails foo server --production --host=0.0.0.0 --port=9000

Reset the instance:

    tails foo reset
