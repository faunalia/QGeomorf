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


class ArcUpstreamDownstream(GeoAlgorithm):
    NETWORK_LAYER = 'NETWORK_LAYER'

    UPDOWN_LAYER = 'UPDOWN_LAYER'

    def getIcon(self):
        return QIcon(os.path.join(pluginPath, 'icons', 'enea.png'))

    def defineCharacteristics(self):
        self.name = 'Find arcs upstream and downstream'
        self.group = 'Geomorf'

        self.addParameter(ParameterVector(self.NETWORK_LAYER,
            self.tr('Stream network'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addOutput(OutputVector(self.UPDOWN_LAYER,
            self.tr('Upstream and downstream arcs detected')))

    def processAlgorithm(self, progress):
        network = dataobjects.getObjectFromUri(
            self.getParameterValue(self.NETWORK_LAYER))

        # Ensure that nodes already indexed
        idxDownNodeId = findField(network, 'DownNodeId')
        idxUpNodeId = findField(network, 'UpNodeId')
        if idxDownNodeId == -1 or idxUpNodeId == -1:
            raise GeoAlgorithmExecutionException(
                self.tr('Seems nodes are not indexed. Please run node '
                        'indexing tool first and try again.'))

        # First add new fields to the network layer
        networkProvider = network.dataProvider()

        (idxDownArcId, fieldList) = findOrCreateField(network,
            network.pendingFields(), 'DownArcId', QVariant.Int, 10, 0)
        (idxUpArcId, fieldList) = findOrCreateField(network, fieldList,
            'UpArcId', QVariant.String, 250, 0)
        (idxLength, fieldList) = findOrCreateField(network, fieldList,
            'Length', QVariant.Double, 20, 6)
        (idxLenDown, fieldList) = findOrCreateField(network, fieldList,
            'LengthDown', QVariant.Double, 20, 6)
        (idxLenUp, fieldList) = findOrCreateField(network, fieldList,
            'LengthUp', QVariant.Double, 20, 6)

        writer = self.getOutputFromName(self.UPDOWN_LAYER).getVectorWriter(
            fieldList.toList(), networkProvider.geometryType(),
            networkProvider.crs())

        # Generate arc adjacency dictionary
        # Algorithm at pages 79-80 "Automated AGQ4Vector Watershed.pdf"
        progress.setInfo(self.tr('Generating arc adjacency dictionary...'))
        self.arcsPerNode = arcsAadjacencyDictionary(network)

        myNetwork, arcsPerNodeId = makeHelperDictionaries(network)

        # Write output file
        for f in network.getFeatures():
            writer.addFeature(f)
        del writer

        vl = QgsVectorLayer(self.getOutputValue(self.UPDOWN_LAYER), 'tmp', 'ogr')
        provider = vl.dataProvider()
        for f in vl.getFeatures():
            fid = f.id()

            # Determine upstream node id
            upNodeId = f['UpNodeId']

            attrs = {idxDownArcId:fid}
            changes = dict()
            ids = []

            # Iterate over all arcs connected to the upstream node with
            # given id, skipping current arc
            for i in arcsPerNodeId[upNodeId]:
                if i != fid:
                    # Modify DownArcId
                    changes[i] = attrs
                    # Collect ids of the arcs located upstream
                    ids.append(str(i))

            provider.changeAttributeValues(changes)
            provider.changeAttributeValues({fid:{idxUpArcId:','.join(ids)}})

            # Also calculate length of the current arc
            provider.changeAttributeValues({fid:{idxLength:f.geometry().length()}})

        # Calculate length upstream for arcs
        # Algorithm at pages 61-62 "Automated AGQ4Vector Watershed.pdf"
        progress.setInfo(self.tr('Calculating length upstream...'))
        req = QgsFeatureRequest()
        # Iterate over upsteram node ids starting from the last ones
        # which represents source arcs
        for nodeId in sorted(myNetwork.keys(), reverse=True):
            f = vl.getFeatures(req.setFilterFid(myNetwork[nodeId])).next()
            arcLen = f['Length'] if f['Length'] else 0.0
            upstreamArcs = f['UpArcId']
            if not upstreamArcs:
                provider.changeAttributeValues({f.id():{idxLenUp: arcLen}})
            else:
                length = []
                for i in upstreamArcs.split(','):
                    f = vl.getFeatures(req.setFilterFid(int(i))).next()
                    if f['LengthUp']:
                        length.append(f['LengthUp'])
                    upLen = max(length) if len(length) > 0  else 0.0
                provider.changeAttributeValues({myNetwork[nodeId]:{idxLenUp:arcLen + upLen}})

        # Calculate length downstream for arcs
        # Algorithm at pages 62-63 "Automated AGQ4Vector Watershed.pdf"
        progress.setInfo(self.tr('Calculating length downstream...'))
        first = True
        # Iterate over upsteram node ids starting from the first one
        # which represents downstream node of the outlet arc
        for nodeId in sorted(myNetwork.keys()):
            f = vl.getFeatures(req.setFilterFid(myNetwork[nodeId])).next()
            # for outlet arc downstream length set to zero
            if first:
                provider.changeAttributeValues({myNetwork[nodeId]:{idxLenDown:0.0}})
                first = False
                continue

            arcLen = f['Length'] if f['Length'] else 0.0
            downArcId = f['DownArcId']
            f = vl.getFeatures(req.setFilterFid(downArcId)).next()
            lenDown = f['LengthDown'] if f['LengthDown'] else 0.0
            provider.changeAttributeValues({myNetwork[nodeId]:{idxLenDown: arcLen + lenDown}})
