# -*- coding: utf-8 -*-

import os

from PyQt4.QtGui import QIcon

from qgis.core import NULL, QgsFeatureRequest

from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.GeoAlgorithmExecutionException import \
    GeoAlgorithmExecutionException

from processing.core.parameters import ParameterVector
from processing.core.outputs import OutputVector

from processing.tools import dataobjects
from processing.tools import vector

from QGeomorf.tools import *


pluginPath = os.path.dirname(__file__)


class StrahlerOrder(GeoAlgorithm):
    NETWORK_LAYER = 'NETWORK_LAYER'

    STRAHLER_ORDER = 'STRAHLER_ORDER'

    def getIcon(self):
        return QIcon(os.path.join(pluginPath, 'icons', 'enea.png'))

    def defineCharacteristics(self):
        self.name = 'Assign Strahler orders'
        self.group = 'Geomorf'

        self.addParameter(ParameterVector(self.NETWORK_LAYER,
            self.tr('Stream network'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addOutput(OutputVector(
            self.STRAHLER_ORDER, self.tr('Strahler orders')))

    def processAlgorithm(self, progress):
        network = dataobjects.getObjectFromUri(
            self.getParameterValue(self.NETWORK_LAYER))

        # Ensure that upstream and downstream arc detected
        idxUpArcId= findField(network, 'UpArcId')
        if idxUpArcId == -1:
            raise GeoAlgorithmExecutionException(
                self.tr('Seems upstream and downstream arcs is not set. '
                        'Please run corresponding tool and try again.'))

        # First add new fields to the network layer
        networkProvider = network.dataProvider()

        (idxStrahler, fieldList) = findOrCreateField(network,
            network.pendingFields(), 'StrahOrder', QVariant.Int, 10, 0)

        writer = self.getOutputFromName(self.STRAHLER_ORDER).getVectorWriter(
            fieldList.toList(), networkProvider.geometryType(),
            networkProvider.crs())

        # Generate helper dictionaries
        myNetwork, arcsPerNodeId = makeHelperDictionaries(network)

        # Write output file
        for f in network.getFeatures():
            writer.addFeature(f)
        del writer

        vl = QgsVectorLayer(self.getOutputValue(self.STRAHLER_ORDER), 'tmp', 'ogr')
        provider = vl.dataProvider()

        # calculate Strahler orders
        # Algorithm at pages 65-66 "Automated AGQ4Vector Watershed.pdf"
        req = QgsFeatureRequest()
        progress.setInfo(self.tr('Calculating Strahler orders...'))
        # Iterate over upsteram node ids starting from the last ones
        # which represents source arcs
        for nodeId in sorted(myNetwork.keys(), reverse=True):
            f = vl.getFeatures(req.setFilterFid(myNetwork[nodeId])).next()
            fid = f.id()
            upstreamArcs = f['UpArcId']
            if upstreamArcs == NULL:
                provider.changeAttributeValues({fid:{idxStrahler: 1}})
            else:
                orders = []
                for i in upstreamArcs.split(','):
                    f = vl.getFeatures(req.setFilterFid(int(i))).next()
                    if f['StrahOrder']:
                        orders.append(f['StrahOrder'])
                orders.sort(reverse=True)
                if len(orders) == 1:
                    order = orders[0]
                elif len(orders) >= 2:
                    diff = orders[0] - orders[1]
                    if diff == 0:
                        order = orders[0] + 1
                    else:
                        order = max([orders[0], orders[1]])
                provider.changeAttributeValues({fid:{idxStrahler: order}})
