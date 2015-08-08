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


class NodeIndexing(GeoAlgorithm):
    NETWORK_LAYER = 'NETWORK_LAYER'

    INDEXED = 'INDEXED'

    def getIcon(self):
        return QIcon(os.path.join(pluginPath, 'icons', 'enea.png'))

    def defineCharacteristics(self):
        self.name = 'Node indexing'
        self.group = 'Geomorf'

        self.addParameter(ParameterVector(self.NETWORK_LAYER,
            self.tr('Stream network (outlet arc should be selected)'),
            [ParameterVector.VECTOR_TYPE_LINE]))

        self.addOutput(OutputVector(self.INDEXED,
            self.tr('Network with indexed nodes')))

    def processAlgorithm(self, progress):
        network = dataobjects.getObjectFromUri(
            self.getParameterValue(self.NETWORK_LAYER))

        # Ensure that outlet arc is selected
        if network.selectedFeatureCount() != 1:
            raise GeoAlgorithmExecutionException(
                self.tr('Seems oulet arc is not selected. Select outlet'
                        'arc in the stream network layer and try again.'))

        # First add new fields to the network layer
        networkProvider = network.dataProvider()

        (idxDownNodeId, fieldList) = findOrCreateField(network,
                network.pendingFields(), 'DownNodeId', QVariant.Int, 10, 0)
        (idxUpNodeId, fieldList) = findOrCreateField(network, fieldList,
                'UpNodeId', QVariant.Int, 10, 0)
        network.updateFields()

        writer = self.getOutputFromName(self.INDEXED).getVectorWriter(
            fieldList.toList(), networkProvider.geometryType(),
            networkProvider.crs())

        # Generate arc adjacency dictionary
        # Algorithm at pages 79-80 "Automated AGQ4Vector Watershed.pdf"
        progress.setInfo(self.tr('Generating arc adjacency dictionary...'))
        self.arcsPerNode = arcsAadjacencyDictionary(network)

        # Node indexing
        # Algorithm at pages 80-81 "Automated AGQ4Vector Watershed.pdf"
        progress.setInfo(self.tr('Indexing nodes...'))
        self.dwUpNodesId = dict()

        # Outlet arc and its upstream node
        outletArc = network.selectedFeatures()[0]
        upNode = outletArc.geometry().asPolyline()[-1]

        # Dictionary for storing node indexes per arc.
        # For outlet arc we assign -1 for downstream and 0 for upstream nodes
        self.dwUpNodesId[outletArc.id()] = [-1, 0]
        # Current node id
        self.nodeId = 0

        # Start recursive node indexing procedure
        self.nodeIndexing(outletArc, upNode)

        # Write output file
        progress.setInfo(self.tr('Writing output...'))

        for f in network.getFeatures():
            writer.addFeature(f)
        del writer

        vl = QgsVectorLayer(self.getOutputValue(self.INDEXED), 'tmp', 'ogr')
        provider = vl.dataProvider()
        for i in self.dwUpNodesId.keys():
            nodeIds = self.dwUpNodesId[i]
            attrs = {idxDownNodeId:nodeIds[0], idxUpNodeId:nodeIds[1]}
            provider.changeAttributeValues({i: attrs})

    def nodeIndexing(self, arc, upNode):
        if len(self.arcsPerNode[upNode]) != 1:
            # iterate over arcs connected to given node
            for f in self.arcsPerNode[upNode]:
                if f.id() != arc.id():
                    polyline = f.geometry().asPolyline()
                    fNode = polyline[0]
                    tNode = polyline[-1]

                    self.nodeId += 1

                    self.dwUpNodesId[f.id()] = [self.dwUpNodesId[arc.id()][1], self.nodeId]

                    if upNode != fNode:
                        self.nodeIndexing(f, fNode)
                    else:
                        self.nodeIndexing(f, tNode)
