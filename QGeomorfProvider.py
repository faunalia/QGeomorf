# -*- coding: utf-8 -*-

import os

from PyQt4.QtGui import QIcon

from processing.core.AlgorithmProvider import AlgorithmProvider
from processing.core.ProcessingConfig import Setting, ProcessingConfig

from QGeomorf.Geomorf import Geomorf


pluginPath = os.path.dirname(__file__)


class QGeomorfProvider(AlgorithmProvider):

    def __init__(self):
        AlgorithmProvider.__init__(self)

        self.activate = False

        self.alglist = [Geomorf()]
        for alg in self.alglist:
            alg.provider = self

    def initializeSettings(self):
        AlgorithmProvider.initializeSettings(self)

    def unload(self):
        AlgorithmProvider.unload(self)

    def getName(self):
        return 'QGeomorf'

    def getDescription(self):
        return 'QGeomorf'

    def getIcon(self):
        return QIcon(os.path.join(pluginPath, 'icons', 'enea.png'))

    def _loadAlgorithms(self):
        self.algs = self.alglist
