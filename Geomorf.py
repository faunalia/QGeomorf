# -*- coding: utf-8 -*-

import os

from PyQt4.QtGui import QIcon

from qgis.core import QgsMapLayerRegistry, QgsFeatureRequest

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

        # create point layer with nodes. It is really necessary???
        progress.setInfo(self.tr('Generating network nodes...'))
        nodes = makePoints(network)
        QgsMapLayerRegistry.instance().addMapLayer(nodes)

        # generate arc adjacency dictionary
        progress.setInfo(self.tr('Generating arc adjacency dictionary...'))
        self.arcsPerNode = makeDictionary(network)

        # node indexing
        progress.setInfo(self.tr('Indexing nodes...'))
        self.dwUpNodesId = dict()
        fid = network.selectedFeaturesIds()[0]
        self.dwUpNodesId[fid] = [-1, 0]
        self.nodeId = 0

        f = network.selectedFeatures()[0]
        node = f.geometry().asPolyline()[-1]
        self.nodeIndexing(f, node)

        # write node indices to attributes
        progress.setInfo(self.tr('Assign indices...'))
        p = network.dataProvider()
        p.addAttributes([QgsField('myfNode', QVariant.Int, '', 10),
                         QgsField('mytnode', QVariant.Int, '', 10)])
        network.updateFields()
        ifNode = network.fieldNameIndex('myfNode')
        itNode = network.fieldNameIndex('mytnode')
        req = QgsFeatureRequest()
        for fid in self.dwUpNodesId.keys():
            ids = self.dwUpNodesId[fid]
            attrs = {ifNode:ids[0], itNode:ids[1]}
            p.changeAttributeValues({fid: attrs})

        # find upstream and downstream arcs
        arcsPerNodeId = dict()
        for f in network.getFeatures():
            if f['myfNode'] not in arcsPerNodeId:
                arcsPerNodeId[f['myfNode']] = [f.id()]
            else:
                arcsPerNodeId[f['myfNode']].append(f.id())

            if f['mytNode'] not in arcsPerNodeId:
                arcsPerNodeId[f['mytNode']] = [f.id()]
            else:
                arcsPerNodeId[f['mytNode']].append(f.id())

        p.addAttributes([QgsField('downArcId', QVariant.Int, '', 10),
                         QgsField('upArcId', QVariant.String, '', 250)])
        network.updateFields()
        idxDown = network.fieldNameIndex('downArcId')
        idxUp = network.fieldNameIndex('upArcId')

        for f in network.getFeatures():
            upNodeId = f['mytNode']
            attrs = {idxDown:f.id()}
            changes = dict()
            ids = []
            for i in arcsPerNodeId[upNodeId]:
                if i != f.id():
                    changes[i] = attrs
                    ids.append(str(i))
            p.changeAttributeValues(changes)
            p.changeAttributeValues({f.id():{idxUp:','.join(ids)}})

    def nodeIndexing(self, arc, node):
        if len(self.arcsPerNode[node]) != 1:
            for f in self.arcsPerNode[node]:
                if f.id() != arc.id():
                    polyline = f.geometry().asPolyline()
                    fNode = polyline[0]
                    tNode = polyline[-1]

                    self.nodeId += 1

                    self.dwUpNodesId[f.id()] = [self.dwUpNodesId[arc.id()][1], self.nodeId]

                    if node != fNode:
                        self.nodeIndexing(f, fNode)
                    else:
                        self.nodeIndexing(f, tNode)
