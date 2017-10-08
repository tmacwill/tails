import argparse
import atexit
import importlib
import json
import os
import multiprocessing
import sanic
import signal
import subprocess
import stellata
import stellata.schema
import sys
import time
import watchdog.events
import watchdog.observers

_commands = []

class ServerReloadHandler(watchdog.events.PatternMatchingEventHandler):
    patterns = ['*.py']

    def __init__(self, process, app, host, port, production):
        super().__init__()
        self.process = process
        self.app = app
        self.host = host
        self.port = port
        self.production = production

    def on_created(self, event):
        self.reload(event)

    def on_modified(self, event):
        self.reload(event)

    def reload(self, event):
        print('%s changed, reloading' % event.src_path)
        atexit.unregister(self.process.terminate)
        self.process.terminate()
        self.process = _start_server_process(self.app, self.host, self.port, self.production)

class _Command:
    def block(self, args):
        raise NotImplementedError()

    def command(self):
        raise NotImplementedError()

    def parse(self, parser):
        raise NotImplementedError()

    def run(self, app, args):
        raise NotImplementedError()

class Build(_Command):
    def block(self, args):
        return args['watch']

    def command(self):
        return 'build'

    def parse(self, parser):
        parser.add_argument('--production', action='store_true', default=False, help='Build files in production mode')
        parser.add_argument('--watch', action='store_true', default=False, help='Watch the working directory for changes')

    def run(self, app, args):
        process = _build(args['production'], args['watch'])

        # if not in watch mode, then wait for process to complete
        if not args['watch']:
            process.wait()

class Migrate(_Command):
    def block(self, args):
        return False

    def command(self):
        return 'migrate'

    def parse(self, parser):
        parser.add_argument('--dry-run', action='store_true', default=False, help='Do a try run, without executing any SQL')
        parser.add_argument('--debug', action='store_true', default=False, help='Print SQL statements as they are executed')

    def run(self, app, args):
        module = importlib.import_module(app)
        print(stellata.schema.migrate(module.db, execute=not args['dry_run'], debug=args['debug']))

class Reset(_Command):
    def block(self, args):
        return False

    def command(self):
        return 'reset'

    def parse(self, parser):
        return

    def run(self, app, args):
        module = importlib.import_module(app)
        stellata.schema.drop_tables_and_lose_all_data(module.db, execute=True)
        stellata.schema.migrate(module.db, execute=True)

class Server(_Command):
    def block(self, args):
        return True

    def command(self):
        return 'server'

    def parse(self, parser):
        parser.add_argument(
            '--build',
            action='store_true',
            default=False,
            help='Build files in addition to running server'
        )
        parser.add_argument('--celery', type=str, action='append', default=[], help='Run celery worker')
        parser.add_argument('--dependency', type=str, action='append', default=[], help='Run dependency')
        parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to run server on')
        parser.add_argument('--port', type=int, default=9000, help='Port to run server on')
        parser.add_argument(
            '--production',
            action='store_true',
            default=False,
            help='Run the server in production mode'
        )
        parser.add_argument(
            '--watch',
            action='store_true',
            default=False,
            help='Watch the working directory for changes'
        )

    def run(self, app, args):
        host = args['host']
        port = args['port']
        celery = args['celery']
        dependencies = args['dependencies']
        production = args['production']
        watch = args['watch']
        build = args['build']

        if not production:
            print('Running %s on %s:%s' % (app, host, port))

        # start webpack process
        if build:
            _build(production, watch)

        # start celery processes
        for name in celery:
            _celery(name)

        # start celery processes
        for command in dependencies:
            _dependency(command)

        # use watchdog to monitor changes to working directory and reload server on change
        server_process = _start_server_process(app, host, port, production)
        if watch:
            handler = ServerReloadHandler(server_process, app, host, port, production)
            observer = watchdog.observers.Observer()
            observer.schedule(handler, path='.', recursive=True)
            observer.start()

class Test(_Command):
    def block(self, args):
        return False

    def command(self):
        return 'test'

    def parse(self, parser):
        parser.add_argument('-t', '--tests', action='append', default=[], help='Tests to run')

    def run(self, app, args):
        os.system('TEST=1 python -m unittest %s' % ' '.join(args['tests']))

def _build(production=False, watch=False):
    if not os.path.isfile('./webpack.config.js'):
        return

    webpack = './node_modules/webpack/bin/webpack.js'
    if not os.path.isfile(webpack):
        webpack = 'webpack'

    args = [webpack, '--progress']
    env = os.environ.copy()

    if production:
        env['NODE_ENV'] = 'production'
        args += ['-p']

    if watch:
        args += ['--watch']

    process = subprocess.Popen(args, env=env)
    atexit.register(process.terminate)
    return process

def _celery(name):
    process = subprocess.Popen(['celery', 'worker', '-A', name, '-l', 'info'])
    atexit.register(process.terminate)
    return process

def _dependency(command):
    process = subprocess.Popen(command.split(' '))
    atexit.register(process.terminate)
    return process

def _exit(signal, frame):
    sys.exit(0)

def _register_command(command, subparsers):
    global _commands
    _commands.append(command)
    parser = subparsers.add_parser(command.command())
    command.parse(parser)

def _run_server(app, host, port, production):
    # decrease log level if running in production mode
    if production:
        sanic.config.LOGGING['loggers']['sanic']['level'] = 'INFO'

    kwargs = {
        'host': host,
        'port': port,
        'debug': not production,
    }

    # dynamically import module passed as arg
    module = importlib.import_module(app)
    module.app.run(**kwargs)

def _start_server_process(app, host, port, production):
    # run server in a separate process and return the handle
    process = multiprocessing.Process(target=_run_server, args=(app, host, port, production))
    process.start()
    atexit.register(process.terminate)
    return process

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('app')
    parser.add_argument('--config', type=str, default=None, help='Path to config')

    # create subparser, then register each command to it
    subparsers = parser.add_subparsers(dest='command')
    _register_command(Build(), subparsers)
    _register_command(Migrate(), subparsers)
    _register_command(Reset(), subparsers)
    _register_command(Server(), subparsers)
    _register_command(Test(), subparsers)

    args = vars(parser.parse_args())
    if args['config'] and os.path.isfile(args['config']):
        with open(args['config'], 'r') as f:
            args.update(json.loads(f.read()))

    block = False
    path = os.getcwd()
    for command in _commands:
        if command.command() == args['command']:
            if command.block(args):
                block = True

            os.chdir(path)
            os.chdir(args['app'] + '/../')
            sys.path.append(os.getcwd())
            command.run(args['app'].split('/')[-1], args)

    # if any command is blocking, then wait for the user to exit
    if block:
        signal.signal(signal.SIGINT, _exit)
        signal.pause()

if __name__ == "__main__":
    main()
