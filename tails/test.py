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
        log_config = sanic.config.LOGGING
        log_config['loggers']['sanic']['level'] = 'INFO'
        log_config['loggers']['sanic']['handlers'] = []
        log_config['loggers']['network']['level'] = 'CRITICAL'
        log_config['loggers']['network']['handlers'] = []

        # start with a fresh database
        for model in stellata.model.registered():
            model.truncate()
