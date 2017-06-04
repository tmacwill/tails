import sanic
import sanic.config
import stellata
import stellata.model
import unittest
import warnings

class TestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()

        # set up sane console output
        warnings.simplefilter('ignore')
        sanic.config.LOGGING['handlers'].pop('accessTimedRotatingFile', None)
        sanic.config.LOGGING['handlers'].pop('errorTimedRotatingFile', None)
        sanic.config.LOGGING['loggers']['sanic']['level'] = 'DEBUG'
        sanic.config.LOGGING['loggers']['sanic']['handlers'] = []
        sanic.config.LOGGING['loggers']['network']['level'] = 'CRITICAL'
        sanic.config.LOGGING['loggers']['network']['handlers'] = []

        # start with a fresh database
        for model in stellata.model.registered():
            model.truncate()
