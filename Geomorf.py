# -*- coding: utf-8 -*-

import os

from PyQt4.QtGui import QIcon

from qgis.core import QgsGeometry, QgsFeatureRequest

from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.GeoAlgorithmExecutionException import \
    GeoAlgorithmExecutionException

from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputTable

from processing.tools import dataobjects
from processing.tools import vector

from QGeomorf.tools import *


pluginPath = os.path.dirname(__file__)


class Geomorf(GeoAlgorithm):
    NETWORK_LAYER = 'NETWORK_LAYER'
    UPSTREAM_NODE = 'UPSTREAM_NODE'
    FIELD_NAME = 'FIELD_NAME'

    BIFURCATION_PARAMS = 'BIFURCATION_PARAMS'

    def getIcon(self):
        return QIcon(os.path.join(pluginPath, 'icons', 'enea.png'))

    def defineCharacteristics(self):
        self.name = 'Geomorfic parameters calculation'
        self.group = 'Geomorf'

        self.addParameter(ParameterVector(self.NETWORK_LAYER,
            self.tr('Stream network'), [ParameterVector.VECTOR_TYPE_LINE]))
        self.addParameter(ParameterVector(self.UPSTREAM_NODE,
            self.tr('Upstream node of the outlet arc'),
            [ParameterVector.VECTOR_TYPE_POINT]))
        self.addParameter(ParameterTableField(self.FIELD_NAME,
            self.tr('Strahler order field'), self.NETWORK_LAYER,
            ParameterTableField.DATA_TYPE_NUMBER))

        self.addOutput(OutputTable(
            self.BIFURCATION_PARAMS, self.tr('Bifurcation parameters')))

    def processAlgorithm(self, progress):
        network = dataobjects.getObjectFromUri(
            self.getParameterValue(self.NETWORK_LAYER))
        outlet = dataobjects.getObjectFromUri(
            self.getParameterValue(self.UPSTREAM_NODE))

        strahlerField = self.getParameterValue(self.FIELD_NAME)

        # ensure that outlet arc is selected
        if network.selectedFeatureCount() != 1:
            raise GeoAlgorithmExecutionException(
                self.tr('Seems oulet arc is not selected. Select outlet'
                        'arc in the stream network layer and try again.'))

        upNode = outlet.getFeatures().next()
        upNodeGeom = QgsGeometry(upNode.geometry())

        # generate arc adjacency dictionary
        arcsPerNode = makeDictionary(network)

        # node indexing
