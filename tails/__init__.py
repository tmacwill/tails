import sanic.config

sanic.config.LOGGING['handlers'].pop('accessTimedRotatingFile', None)
sanic.config.LOGGING['handlers'].pop('errorTimedRotatingFile', None)
sanic.config.LOGGING['loggers']['sanic']['level'] = 'DEBUG'
sanic.config.LOGGING['loggers']['sanic']['handlers'] = []
sanic.config.LOGGING['loggers']['network']['level'] = 'CRITICAL'
sanic.config.LOGGING['loggers']['network']['handlers'] = []
