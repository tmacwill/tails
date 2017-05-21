import argparse
import atexit
import importlib
import os
import multiprocessing
import sanic
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

    def __init__(self, process, args):
        super().__init__()
        self.process = process
        self.args = args

    def on_created(self, event):
        self.reload(event)

    def on_modified(self, event):
        self.reload(event)

    def reload(self, event):
        print('%s changed, reloading' % event.src_path)
        atexit.unregister(self.process.terminate)
        self.process.terminate()
        self.process = _start_server_process(self.args)

class _Command:
    def command(self):
        raise NotImplementedError()

    def parse(self, parser):
        raise NotImplementedError()

    def run(self, args):
        raise NotImplementedError()

class Build(_Command):
    def command(self):
        return 'build'

    def parse(self, parser):
        parser.add_argument('--production', action='store_true', default=False, help='Build files in production mode')
        parser.add_argument('--watch', action='store_true', default=False, help='Watch the working directory for changes')

    def run(self, args):
        process = _build(args.production, args.watch)
        process.wait()

class Migrate(_Command):
    def command(self):
        return 'migrate'

    def parse(self, parser):
        parser.add_argument('--dry-run', action='store_true', default=False, help='Do a try run, without executing any SQL')

    def run(self, args):
        module = importlib.import_module(args.app)
        print(stellata.schema.migrate(module.db, execute=not args.dry_run))

class Reset(_Command):
    def command(self):
        return 'reset'

    def parse(self, parser):
        return

    def run(self, args):
        module = importlib.import_module(args.app)
        stellata.schema.drop_tables_and_lose_all_data(module.db, execute=True)
        stellata.schema.migrate(module.db, execute=True)

class Server(_Command):
    def command(self):
        return 'server'

    def parse(self, parser):
        parser.add_argument(
            '--build',
            action='store_true',
            default=False,
            help='Build files in addition to running server'
        )
        parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to run server on')
        parser.add_argument('--port', type=int, default=9000, help='Port to run server on')
        parser.add_argument(
            '--production',
            action='store_true',
            default=False,
            help='Run the server in production mode'
        )
        parser.add_argument('--watch', action='store_true', help='Watch the working directory for changes')

    def run(self, args):
        if not args.production:
            print('Running server on %s:%s' % (args.host, args.port))

        if args.build:
            build_process = _build(args.production, args.watch)

        # if we're not in watch mode, we can just block on the server process
        if not args.watch:
            _run_server(args)
            return

        # use watchdog to monitor changes to working directory and reload server on change
        server_process = _start_server_process(args)
        handler = ServerReloadHandler(server_process, args)
        observer = watchdog.observers.Observer()
        observer.schedule(handler, path='.', recursive=True)
        observer.start()

        # block on server process
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

def _build(production=False, watch=False):
    args = ['./node_modules/webpack/bin/webpack.js', '--progress']
    env = os.environ.copy()

    if production:
        env['NODE_ENV'] = 'production'
        args += ['-p']

    if watch:
        args += ['--watch']

    process = subprocess.Popen(args, env=env)
    atexit.register(process.terminate)
    return process

def _register_command(command, subparsers):
    global _commands
    _commands.append(command)
    parser = subparsers.add_parser(command.command())
    command.parse(parser)

def _run_server(args):
    log_config = sanic.config.LOGGING
    log_config['loggers']['sanic']['level'] = 'DEBUG'
    log_config['loggers']['sanic']['handlers'] = []
    log_config['loggers']['network']['level'] = 'CRITICAL'
    log_config['loggers']['network']['handlers'] = []
    if args.production:
        log_config['loggers']['sanic']['level'] = 'INFO'

    kwargs = {
        'host': args.host,
        'port': args.port,
        'debug': not args.production,
        'log_config': log_config,
    }

    # dynamically import module passed as arg
    module = importlib.import_module(args.app)
    module.app.run(**kwargs)

def _start_server_process(args):
    # run server in a separate process and return the handle
    process = multiprocessing.Process(target=_run_server, args=(args,))
    process.start()
    atexit.register(process.terminate)
    return process

def main():
    sys.path.append(os.getcwd())
    parser = argparse.ArgumentParser()
    parser.add_argument('app')

    # create subparser, then register each command to it
    subparsers = parser.add_subparsers(dest='command')
    _register_command(Build(), subparsers)
    _register_command(Migrate(), subparsers)
    _register_command(Reset(), subparsers)
    _register_command(Server(), subparsers)

    args = parser.parse_args()
    for command in _commands:
        if command.command() == args.command:
            command.run(args)

if __name__ == "__main__":
    main()
