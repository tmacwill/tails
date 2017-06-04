import argparse
import atexit
import importlib
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

    def run(self, app, args, index=0):
        raise NotImplementedError()

class Build(_Command):
    def block(self, args):
        return args.watch

    def command(self):
        return 'build'

    def parse(self, parser):
        parser.add_argument('--production', action='store_true', default=False, help='Build files in production mode')
        parser.add_argument('--watch', action='store_true', default=False, help='Watch the working directory for changes')

    def run(self, app, args, index=0):
        process = _build(args.production, args.watch)

        # if not in watch mode, then wait for process to complete
        if not args.watch:
            process.wait()

class Migrate(_Command):
    def block(self, args):
        return False

    def command(self):
        return 'migrate'

    def parse(self, parser):
        parser.add_argument('--dry-run', action='store_true', default=False, help='Do a try run, without executing any SQL')
        parser.add_argument('--debug', action='store_true', default=False, help='Print SQL statements as they are executed')

    def run(self, app, args, index=0):
        module = importlib.import_module(app)
        print(stellata.schema.migrate(module.db, execute=not args.dry_run, debug=args.debug))

class Reset(_Command):
    def block(self, args):
        return False

    def command(self):
        return 'reset'

    def parse(self, parser):
        return

    def run(self, app, args, index=0):
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
        parser.add_argument('--host', type=str, action='append', help='Host to run server on')
        parser.add_argument('--port', type=int, action='append', help='Port to run server on')
        parser.add_argument(
            '--production',
            action='store_true',
            default=False,
            help='Run the server in production mode'
        )
        parser.add_argument('--watch', action='store_true', help='Watch the working directory for changes')

    def run(self, app, args, index=0):
        host = '0.0.0.0'
        if args.host and index < len(args.host):
            host = args.host[index]

        port = 9000 + index
        if args.port and index < len(args.port):
            port = args.port[index]

        production = args.production
        if not production:
            print('Running %s on %s:%s' % (app, host, port))

        if args.build:
            build_process = _build(production, args.watch)

        # use watchdog to monitor changes to working directory and reload server on change
        server_process = _start_server_process(app, host, port, production)
        if args.watch:
            handler = ServerReloadHandler(server_process, app, host, port, production)
            observer = watchdog.observers.Observer()
            observer.schedule(handler, path='.', recursive=True)
            observer.start()

def _build(production=False, watch=False):
    webpack = './node_modules/webpack/bin/webpack.js'
    if not os.path.isfile(webpack):
        return

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
    del sanic.config.LOGGING['handlers']['accessTimedRotatingFile']
    del sanic.config.LOGGING['handlers']['errorTimedRotatingFile']
    sanic.config.LOGGING['loggers']['sanic']['level'] = 'DEBUG'
    sanic.config.LOGGING['loggers']['sanic']['handlers'] = []
    sanic.config.LOGGING['loggers']['network']['level'] = 'CRITICAL'
    sanic.config.LOGGING['loggers']['network']['handlers'] = []

    parser = argparse.ArgumentParser()
    parser.add_argument('apps', nargs=argparse.REMAINDER)

    # create subparser, then register each command to it
    subparsers = parser.add_subparsers(dest='command')
    _register_command(Build(), subparsers)
    _register_command(Migrate(), subparsers)
    _register_command(Reset(), subparsers)
    _register_command(Server(), subparsers)

    block = False
    args = parser.parse_args()
    path = os.getcwd()
    for command in _commands:
        if command.command() == args.command:
            if command.block(args):
                block = True

            for i, app in enumerate(args.apps):
                os.chdir(path)
                os.chdir(app + '/../')
                sys.path.append(os.getcwd())
                command.run(app.split('/')[-1], args, i)

    # if any command is blocking, then wait for the user to exit
    if block:
        signal.signal(signal.SIGINT, _exit)
        signal.pause()

if __name__ == "__main__":
    main()
