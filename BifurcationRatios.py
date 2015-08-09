# -*- coding: utf-8 -*-

import os

from PyQt4.QtGui import QIcon

from qgis.core import NULL, QgsFeatureRequest

from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.GeoAlgorithmExecutionException import \
    GeoAlgorithmExecutionException

from processing.core.parameters import ParameterVector
from processing.core.outputs import OutputTable

from processing.tools import dataobjects
from processing.tools import vector

from QGeomorf.tools import *


pluginPath = os.path.dirname(__file__)


class BifurcationRatios(GeoAlgorithm):
    NETWORK_LAYER = 'NETWORK_LAYER'

    ORDER_FREQUENCY = 'ORDER_FREQUENCY'
    BIFURCATION_PARAMS = 'BIFURCATION_PARAMS'

    def getIcon(self):
        return QIcon(os.path.join(pluginPath, 'icons', 'enea.png'))

    def defineCharacteristics(self):
        self.name = 'Order frequency and bifurcation ratios'
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

        # Ensure that Strahler orders assigned
        idxStrahler= findField(network, 'StrahOrder')
        if idxStrahler == -1:
            raise GeoAlgorithmExecutionException(
                self.tr('Seems Strahler orders is not assigned. '
                        'Please run corresponding tool and try again.'))

        # Generate helper dictionaries
        myNetwork, arcsPerNodeId = makeHelperDictionaries(network)

        # Calculate order frequency
        progress.setInfo(self.tr('Calculating order frequency...'))

        maxOrder = int(network.maximumValue(idxStrahler))
        ordersFrequency = dict()
        bifRatios = dict()

        # Initialize dictionaries
        for i in xrange(1, maxOrder + 1):
            ordersFrequency[i] = dict(N=0.0, Ndu=0.0, Na=0.0)
            bifRatios[i] = dict(Rbu=0.0, Rbdu=0.0, Ru=0.0)

        req = QgsFeatureRequest()
        for i in xrange(1, maxOrder + 1):
            req.setFilterExpression('"StrahOrder" = %s' % i)
            for f in network.getFeatures(req):
                order = int(f['StrahOrder'])
                upstreamArcs = f['UpArcId'].split(',') if f['UpArcId'] else []
                if len(upstreamArcs) == 0:
                    ordersFrequency[i]['N'] += 1.0
                elif len(upstreamArcs) > 1:
                    ordersFrequency[order]['N'] += 1.0
                    for j in upstreamArcs:
                        f = network.getFeatures(QgsFeatureRequest().setFilterFid(int(j))).next()
                        upOrder = int(f['StrahOrder'])
                        diff = upOrder - order
                        if diff == 1:
                            ordersFrequency[upOrder]['Ndu'] += 1.0
                        if diff > 1:
                            ordersFrequency[upOrder]['Na'] += 1.0

        writerOrders = self.getOutputFromName(
            self.ORDER_FREQUENCY).getTableWriter(['order', 'N', 'NDU', 'NA'])

        writerBifrat = self.getOutputFromName(
            self.BIFURCATION_PARAMS).getTableWriter(['order', 'RBD', 'RB', 'RU'])

        # Calculate bifurcation parameters
        progress.setInfo(self.tr('Calculating bifurcation parameters...'))
        for k, v in ordersFrequency.iteritems():
            if k != maxOrder:
                bifRatios[k]['Rbu'] = ordersFrequency[k]['N'] / ordersFrequency[k + 1]['N']
                bifRatios[k]['Rbdu'] = ordersFrequency[k]['Ndu'] / ordersFrequency[k + 1]['N']
            else:
                bifRatios[k]['Rbu'] = 0.0
                bifRatios[k]['Rbdu'] = 0.0

            bifRatios[k]['Ru'] = bifRatios[k]['Rbu'] - bifRatios[k]['Rbdu']

            writerOrders.addRecord([k, v['N'], v['Ndu'], v['Na']])
            writerBifrat.addRecord([k, bifRatios[k]['Rbdu'], bifRatios[k]['Rbu'], bifRatios[k]['Ru']])

        del writerOrders
        del writerBifrat
