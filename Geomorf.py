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

        # Ensure that outlet arc is selected
        if network.selectedFeatureCount() != 1:
            raise GeoAlgorithmExecutionException(
                self.tr('Seems oulet arc is not selected. Select outlet'
                        'arc in the stream network layer and try again.'))

        # First add new fields to the network layer
        networkProvider = network.dataProvider()
        networkProvider.addAttributes(
            [QgsField('StrahOrder', QVariant.Int, '', 10),    # Strahler order
             QgsField('DownNodeId', QVariant.Int, '', 10),    # downstream node id
             QgsField('UpNodeId', QVariant.Int, '', 10),      # upstream node id
             QgsField('DownArcId', QVariant.Int, '', 10),     # downstream arc id
             QgsField('UpArcId', QVariant.String, '', 250),   # comma separated list of upstream arc ids
             QgsField('Length', QVariant.Double, '', 20, 6),  # length of the arc
             QgsField('LengthDown', QVariant.Double, '', 20, 6), # length downstream
             QgsField('LengthUp', QVariant.Double, '', 20, 6)])  # length upstream
        network.updateFields()

        # Determine indexes of the fields
        idxStrahler = network.fieldNameIndex(strahlerField)
        idxMyStrahler = network.fieldNameIndex('StrahOrder')
        idxDownNodeId = network.fieldNameIndex('DownNodeId')
        idxUpNodeId = network.fieldNameIndex('UpNodeId')
        idxDownArcId = network.fieldNameIndex('DownArcId')
        idxUpArcId = network.fieldNameIndex('UpArcId')
        idxLength = network.fieldNameIndex('Length')
        idxLenDown = network.fieldNameIndex('LengthDown')
        idxLenUp = network.fieldNameIndex('LengthUp')

        # Generate arc adjacency dictionary
        progress.setInfo(self.tr('Generating arc adjacency dictionary...'))
        self.arcsPerNode = arcsAadjacencyDictionary(network)

        # Node indexing
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

        # Write node indices to the network layer attributes
        progress.setInfo(self.tr('Assigning indices...'))
        for i in self.dwUpNodesId.keys():
            nodeIds = self.dwUpNodesId[i]
            attrs = {idxDownNodeId:nodeIds[0], idxUpNodeId:nodeIds[1]}
            networkProvider.changeAttributeValues({i: attrs})

        # Mapping between upstream node id from attribute table and  QGIS
        # feature id. Will be used to sort features from the network table
        myNetwork = dict()

        # Find upstream and downstream arc ids for each arc in the stream
        # network layer. First we generate helper arcPerNodeId dictionary
        # with node ids as keys and lists of arc ids connected to this node
        # as values
        arcsPerNodeId = dict()
        for f in network.getFeatures():
            if f['UpNodeId'] not in arcsPerNodeId:
                arcsPerNodeId[f['UpNodeId']] = [f.id()]
            else:
                arcsPerNodeId[f['UpNodeId']].append(f.id())

            if f['DownNodeId'] not in arcsPerNodeId:
                arcsPerNodeId[f['DownNodeId']] = [f.id()]
            else:
                arcsPerNodeId[f['DownNodeId']].append(f.id())

            # Also populate mapping between upstream node id and feature id
            myNetwork[f['UpNodeId']] = f.id()

        # Populating upstream and downstream arc ids
        # Iterate over all arcs in the stream network layer
        for f in network.getFeatures():
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

            networkProvider.changeAttributeValues(changes)
            networkProvider.changeAttributeValues({fid:{idxUpArcId:','.join(ids)}})

            # Also calculate length of the current arc
            networkProvider.changeAttributeValues({fid:{idxLength:f.geometry().length()}})

        # Calculate length upstream for arcs
        progress.setInfo(self.tr('Calculating length upstream...'))
        req = QgsFeatureRequest()
        # Iterate over upsteram node ids starting from the last ones
        # which represents source arcs
        for nodeId in sorted(myNetwork.keys(), reverse=True):
            f = network.getFeatures(req.setFilterFid(myNetwork[nodeId])).next()
            arcLen = f['Length']
            upstreamArcs = f['UpArcId']
            if not upstreamArcs:
                networkProvider.changeAttributeValues({f.id():{idxLenUp: arcLen}})
            else:
                length = []
                for i in upstreamArcs.split(','):
                    f = network.getFeatures(req.setFilterFid(int(i))).next()
                    if f['LengthUp']:
                        length.append(f['LengthUp'])
                    upLen = max(length) if len(length) > 0  else 0.0
                networkProvider.changeAttributeValues({myNetwork[nodeId]:{idxLenUp:arcLen + upLen}})

        # Calculate length downstream for arcs
        progress.setInfo(self.tr('Calculating length downstream...'))
        first = True
        # Iterate over upsteram node ids starting from the first one
        # which represents downstream node of the outlet arc
        for nodeId in sorted(myNetwork.keys()):
            f = network.getFeatures(req.setFilterFid(myNetwork[nodeId])).next()
            # for outlet arc downstream length set to zero
            if first:
                networkProvider.changeAttributeValues({myNetwork[nodeId]:{idxLenDown:0.0}})
                first = False
                continue

            arcLen = f['Length']
            downArcId = f['DownArcId']
            f = network.getFeatures(req.setFilterFid(downArcId)).next()
            lenDown = f['LengthDown'] if f['LengthDown'] else 0.0
            networkProvider.changeAttributeValues({myNetwork[nodeId]:{idxLenDown: arcLen + lenDown}})

        # calculate Strahler orders
        progress.setInfo(self.tr('Calculating Strahler orders...'))
        # Iterate over upsteram node ids starting from the last ones
        # which represents source arcs
        for nodeId in sorted(myNetwork.keys(), reverse=True):
            f = network.getFeatures(req.setFilterFid(myNetwork[nodeId])).next()
            fid = f.id()
            upstreamArcs = f['UpArcId']
            if not upstreamArcs:
                networkProvider.changeAttributeValues({fid:{idxMyStrahler: 1}})
            else:
                orders = []
                for i in upstreamArcs.split(','):
                    f = network.getFeatures(req.setFilterFid(int(i))).next()
                    orders.append(f['StrahOrder'])

                orders.sort()
                if len(orders) >= 2:
                    order = max([orders[0], orders[1] + 1])
                else:
                    order = max([orders[0], 1])
                networkProvider.changeAttributeValues({fid:{idxMyStrahler: order}})

        # Calculate order frequency
        progress.setInfo(self.tr('Calculating order frequency...'))
        maxOrder = int(network.maximumValue(idxStrahler))
        ordersFrequency = dict()
        bifRatios = dict()
        # Initialize dictionaries
        for i in xrange(1, maxOrder + 1):
            ordersFrequency[i] = dict(N=0.0, Ndu=0.0, Na=0.0)
            bifRatios[i] = dict(Rbu=0.0, Rbdu=0.0, Ru=0.0)

        # Iterate over upsteram node ids starting from the last ones
        # which represents source arcs
        for nodeId in sorted(myNetwork.keys(), reverse=True):
            f = network.getFeatures(req.setFilterFid(myNetwork[nodeId])).next()
            u = int(f[strahlerField])

            ordersFrequency[u]['N'] += 1.0

            if f['DownArcId']:
                downArcId = f['downArcId']
                f = network.getFeatures(req.setFilterFid(downArcId)).next()
                downU = int(f[strahlerField])
                if downU - u == 1:
                    ordersFrequency[u]['Ndu'] += 1.0
                elif downU - u > 1:
                    ordersFrequency[u]['Na'] += 1.0

        writerOrders = self.getOutputFromName(
            self.ORDER_FREQUENCY).getTableWriter(['order', 'N', 'Ndu', 'Na'])

        writerBifrat = self.getOutputFromName(
            self.BIFURCATION_PARAMS).getTableWriter(['order', 'Rbu', 'Rbdu', 'Ru'])

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
            writerBifrat.addRecord([k, bifRatios[k]['Rbu'], bifRatios[k]['Rbdu'], bifRatios[k]['Ru']])

        del writerOrders
        del writerBifrat

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
