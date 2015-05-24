# -*- coding: utf-8 -*-

import os
import sys
import inspect

from processing.core.Processing import Processing
from QGeomorf.QGeomorfProvider import QGeomorfProvider


cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]

if cmd_folder not in sys.path:
    sys.path.insert(0, cmd_folder)


class QGeomorfProviderPlugin:

    def __init__(self):
        self.provider = QGeomorfProvider()

    def initGui(self):
        Processing.addProvider(self.provider)

    def unload(self):
        Processing.removeProvider(self.provider)
