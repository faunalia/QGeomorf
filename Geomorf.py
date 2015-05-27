# -*- coding: utf-8 -*-

import os

from PyQt4.QtGui import QIcon

from qgis.core import NULL, QgsFeatureRequest

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

    ORDER_FREQUENCY = 'ORDER_FREQUENCY'
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
            self.ORDER_FREQUENCY, self.tr('Order frequency')))
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

        # mapping between upstream node id and feature id.
        # will be used to sort network table
        mNetwork = dict()

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

            # also populate feature id - upstream node id mapping
            mNetwork[f['mytNode']] = f.id()

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

        # calculate length upstream and downstream
        p.addAttributes([QgsField('length', QVariant.Double, '', 20, 6),
                         QgsField('lenDown', QVariant.Double, '', 20, 6),
                         QgsField('lenUp', QVariant.Double, '', 20, 6)])
        network.updateFields()
        idxLen = network.fieldNameIndex('length')
        idxLenUp = network.fieldNameIndex('lenUp')
        idxLenDown = network.fieldNameIndex('lenDown')

        # lenth of each segment
        for f in network.getFeatures():
            p.changeAttributeValues({f.id():{idxLen: f.geometry().length()}})

        # length upstream
        req = QgsFeatureRequest()
        for k in sorted(mNetwork.keys(), reverse=True):
            f = network.getFeatures(req.setFilterFid(mNetwork[k])).next()
            arcLen = f['length']
            upstreamArcs = f['upArcId']
            if not upstreamArcs:
                p.changeAttributeValues({f.id():{idxLenUp: arcLen}})
            else:
                vals = []
                for j in upstreamArcs.split(','):
                    f = network.getFeatures(req.setFilterFid(int(j))).next()
                    if f['lenUp']:
                        vals.append(f['lenUp'])
                    upLen = max(vals) if len(vals) > 0  else 0.0
                p.changeAttributeValues({mNetwork[k]:{idxLenUp: arcLen + upLen}})

        # length downstream
        first = True
        for k in sorted(mNetwork.keys()):
            print k, mNetwork[k]
            f = network.getFeatures(req.setFilterFid(mNetwork[k])).next()
            if first:
                p.changeAttributeValues({mNetwork[k]:{idxLenDown: 0}})
                first = False
                continue

            arcLen = f['length']
            downArcId = f['downArcId']
            f = network.getFeatures(req.setFilterFid(downArcId)).next()
            lenDown = f['lenDown'] if f['lenDown'] else 0.0
            p.changeAttributeValues({mNetwork[k]:{idxLenDown: arcLen + lenDown}})

        # prepare for bifurcation ratios calculation
        # populate order frequency data
        maxOrder = int(network.maximumValue(network.fieldNameIndex(strahlerField)))
        orders = dict()
        bifrat = dict()
        for i in xrange(maxOrder):
            orders[i + 1] = dict(N=0.0, Ndu=0.0, Na=0.0)
            bifrat[i + 1] = dict(Rbu=0.0, Rbdu=0.0, Ru=0.0)

        for k in sorted(mNetwork.keys(), reverse=True):
            f = network.getFeatures(req.setFilterFid(mNetwork[k])).next()
            u = int(f[strahlerField])

            orders[u]['N'] += 1.0

            if f['downArcId']:
                downId = int(f['downArcId'])
                f = network.getFeatures(req.setFilterFid(downId)).next()
                downU = int(f[strahlerField])
                if downU - u == 1:
                    orders[u]['Ndu'] += 1.0
                elif downU - u > 1:
                    orders[u]['Na'] += 1.0

        writerOrders = self.getOutputFromName(
            self.ORDER_FREQ).getTableWriter(['order', 'N', 'Ndu', 'Na'])

        writerBifrat = self.getOutputFromName(
            self.BIFURCATION_PARAMS).getTableWriter(['order', 'Rbu', 'Rbdu', 'Ru'])

        for k, v in orders.iteritems():
            if k != maxOrder:
                bifrat[k]['Rbu'] = orders[k]['N'] / orders[k + 1]['N']
                bifrat[k]['Rbdu'] = orders[k]['Ndu'] / orders[k + 1]['N']
            else:
                bifrat[k]['Rbu'] = 0.0
                bifrat[k]['Rbdu'] = 0.0

            bifrat[k]['Ru'] = bifrat[k]['Rbu'] - bifrat[k]['Rbdu']

            writerOrders.addRecord([k, v['N'], v['Ndu'], v['Na']])
            writerBifrat.addRecord([k, bifrat[k]['Rbu'], bifrat[k]['Rbdu'], bifrat[k]['Ru']])

        del writerOrders
        del writerBifrat

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
