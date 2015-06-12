# -*- coding: utf-8 -*-

import os

from PyQt4.QtGui import QIcon

from qgis.core import NULL, QgsFeatureRequest

from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.ProcessingConfig import ProcessingConfig, Setting
from processing.core.GeoAlgorithmExecutionException import \
    GeoAlgorithmExecutionException

from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputTable

from processing.tools import dataobjects
from processing.tools import vector

from QGeomorf.GeomorfUtils import GeomorfUtils


pluginPath = os.path.dirname(__file__)


class Geomorf(GeoAlgorithm):
    NETWORK_LAYER = 'NETWORK_LAYER'

    ORDER_FREQUENCY = 'ORDER_FREQUENCY'
    BIFURCATION_PARAMS = 'BIFURCATION_PARAMS'

    def getIcon(self):
        return QIcon(os.path.join(pluginPath, 'icons', 'enea.png'))

    def defineCharacteristics(self):
        self.name = 'Geomorfic parameters calculation'
        self.group = 'Geomorf'

        self.addParameter(ParameterVector(self.NETWORK_LAYER,
            self.tr('Stream network'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addOutput(OutputTable(
            self.ORDER_FREQUENCY, self.tr('Order frequency')))
        self.addOutput(OutputTable(
            self.BIFURCATION_PARAMS, self.tr('Bifurcation parameters')))

    def processAlgorithm(self, progress):
        network = dataobjects.getObjectFromUri(
            self.getParameterValue(self.NETWORK_LAYER))

        # Ensure that outlet arc is selected
        if network.selectedFeatureCount() != 1:
            raise GeoAlgorithmExecutionException(
                self.tr('Seems oulet arc is not selected. Select outlet'
                        'arc in the stream network layer and try again.'))

        layerPath = network.source()

        # Outlet arc id
        outletArcId = network.selectedFeatures()[0].id()

        segfr = self.getOutputFromName(self.ORDER_FREQUENCY)
        bifrat = self.getOutputFromName(self.BIFURCATION_PARAMS)

        processNum = ProcessingConfig.getSetting(GeomorfUtils.MPI_PROCESSES)

        commands = []
        #commands.append(os.path.join(GeomorfUtils.mpiexecPath(), 'mpiexec'))
        #commands.append('mpiexec')
        #commands.append('-n')
        #commands.append(str(processNum))
        commands.append('python')
        commands.append(os.path.join(GeomorfUtils.geomorfPath(), 'qgeomorf.py'))
        commands.append(layerPath)
        commands.append(outletArcId)
        commands.append(segfr.value)
        commands.append(bifrat.value)

        GeomorfUtils.execute(commands, progress)
