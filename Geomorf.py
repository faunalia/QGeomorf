# -*- coding: utf-8 -*-

import os

from PyQt4.QtGui import QIcon

from qgis.core import QgsGeometry, QgsFeatureRequest

from processing.core.GeoAlgorithm import GeoAlgorithm

from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputTable

from processing.tools import dataobjects
from processing.tools import vector


pluginPath = os.path.dirname(__file__)


class Geomorf(GeoAlgorithm):

    def getIcon(self):
        return QIcon(os.path.join(pluginPath, 'icons', 'enea.png'))

    def defineCharacteristics(self):
        self.name = 'Geomorfic parameters calculation'
        self.group = 'Geomorf'

    def processAlgorithm(self, progress):
        pass
