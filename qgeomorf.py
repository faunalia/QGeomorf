# -*- coding: utf-8 -*-

import os
import sys
import csv

from mpi4py import MPI

import sip

try:
    apis = ['QDate', 'QDateTime', 'QString', 'QTextStream', 'QTime', 'QUrl', 'QVariant']
    for api in apis:
        sip.setapi(api, 2)
except ValueError:
    # API has already been set so we can't set it again.
    pass

from PyQt4.QtCore import QVariant

from qgis.core import (NULL, QgsApplication, QgsFeatureRequest, QgsGeometry,
    QgsVectorLayer, QgsFeature, QgsFields, QgsField)


# global variables
arcsPerNode = dict()
dwUpNodesId = dict()
nodeId = 0

qgis_prefix = os.getenv('QGISHOME')


def addFields(layerPath):
    ''' Add new fields to the given vector layer
    '''
    layer = QgsVectorLayer(layerPath, 'network', 'ogr')
    if not layer.isValid():
        print 'Can not create layer.'
        return False

    provider = layer.dataProvider()
    provider.addAttributes(
        [QgsField('StrahOrder', QVariant.Int, '', 10),    # Strahler order
         QgsField('DownNodeId', QVariant.Int, '', 10),    # downstream node id
         QgsField('UpNodeId', QVariant.Int, '', 10),      # upstream node id
         QgsField('DownArcId', QVariant.Int, '', 10),     # downstream arc id
         QgsField('UpArcId', QVariant.String, '', 250),   # comma separated list of upstream arc ids
         QgsField('Length', QVariant.Double, '', 20, 6),  # length of the arc
         QgsField('LengthDown', QVariant.Double, '', 20, 6), # length downstream
         QgsField('LengthUp', QVariant.Double, '', 20, 6)])  # length upstream
    layer.updateFields()
    return True


def arcsAadjacencyDictionary(layerPath):
    '''Build arc adjacency dictionary for the input stream network layer.

    This dictionary is a set of adjacency lists compiled for each node in
    th network.
    '''
    layer = QgsVectorLayer(layerPath, 'network', 'ogr')
    if not layer.isValid():
        print 'Can not create layer.'
        return False


    arcsPerNode = dict()

    for f in layer.getFeatures():
        geom = QgsGeometry(f.geometry())
        polyline = geom.asPolyline()
        fromNode = polyline[0]
        toNode = polyline[-1]

        if fromNode not in arcsPerNode:
            arcsPerNode[fromNode] = [f]
        else:
            arcsPerNode[fromNode].append(f)

        if toNode not in arcsPerNode:
            arcsPerNode[toNode] = [f]
        else:
            arcsPerNode[toNode].append(f)

    return arcsPerNode


def nodeIndexing(arc, upNode):
    global arcsPerNode
    if len(arcsPerNode[upNode]) != 1:
        # iterate over arcs connected to given node
        for f in arcsPerNode[upNode]:
            if f.id() != arc.id():
                polyline = f.geometry().asPolyline()
                fNode = polyline[0]
                tNode = polyline[-1]

                global nodeId
                nodeId += 1

                global dwUpNodesId
                dwUpNodesId[f.id()] = [dwUpNodesId[arc.id()][1], nodeId]

                if upNode != fNode:
                    nodeIndexing(f, fNode)
                else:
                    nodeIndexing(f, tNode)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print 'Incorrect number of arguments.'
        sys.exit(0)

    layerPath = sys.argv[1]
    outletArcId = int(sys.argv[2])

    QgsApplication.setPrefixPath(qgis_prefix, True)
    QgsApplication.initQgis()

    if not addFields(layerPath):
        print 'Failed to add new fields to layer.'
        sys.exit(0)

    layer = QgsVectorLayer(layerPath, 'network', 'ogr')
    if not layer.isValid():
        print 'Can not create layer.'
        sys.exit(0)

    # Determine indexes of the fields
    idxStrahler = layer.fieldNameIndex('StrahOrder')
    idxDownNodeId = layer.fieldNameIndex('DownNodeId')
    idxUpNodeId = layer.fieldNameIndex('UpNodeId')
    idxDownArcId = layer.fieldNameIndex('DownArcId')
    idxUpArcId = layer.fieldNameIndex('UpArcId')
    idxLength = layer.fieldNameIndex('Length')
    idxLenDown = layer.fieldNameIndex('LengthDown')
    idxLenUp = layer.fieldNameIndex('LengthUp')

    # Generate arc adjacency dictionary
    global arcsPerNode
    arcsPerNode = arcsAadjacencyDictionary(layerPath)

    provider = layer.dataProvider()
    request = QgsFeatureRequest()

    # Outlet arc and its upstream node
    outletArc = layer.getFeatures(request.setFilterFid(outletArcId)).next()
    upNode = outletArc.geometry().asPolyline()[-1]

    # Dictionary for storing node indexes per arc.
    # For outlet arc we assign -1 for downstream and 0 for upstream nodes
    global dwUpNodesId
    dwUpNodesId[outletArc.id()] = [-1, 0]
    # Current node id
    global nodeId
    nodeId = 0

    nodeIndexing(outletArc, upNode)

    # Write node indices to the network layer attributes
    global dwUpNodesId
    for i in dwUpNodesId.keys():
        nodeIds = dwUpNodesId[i]
        attrs = {idxDownNodeId:nodeIds[0], idxUpNodeId:nodeIds[1]}
        provider.changeAttributeValues({i: attrs})

    # Mapping between upstream node id from attribute table and  QGIS
    # feature id. Will be used to sort features from the network table
    myNetwork = dict()

    # Find upstream and downstream arc ids for each arc in the stream
    # network layer. First we generate helper arcPerNodeId dictionary
    # with node ids as keys and lists of arc ids connected to this node
    # as values
    arcsPerNodeId = dict()
    for f in layer.getFeatures():
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
    for f in layer.getFeatures():
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
    # Iterate over upsteram node ids starting from the last ones
    # which represents source arcs
    for nodeId in sorted(myNetwork.keys(), reverse=True):
        f = layer.getFeatures(request.setFilterFid(myNetwork[nodeId])).next()
        arcLen = f['Length']
        upstreamArcs = f['UpArcId']
        if not upstreamArcs:
            provider.changeAttributeValues({f.id():{idxLenUp: arcLen}})
        else:
            length = []
            for i in upstreamArcs.split(','):
                f = layer.getFeatures(request.setFilterFid(int(i))).next()
                if f['LengthUp']:
                    length.append(f['LengthUp'])
                upLen = max(length) if len(length) > 0  else 0.0
            provider.changeAttributeValues({myNetwork[nodeId]:{idxLenUp:arcLen + upLen}})

    # Calculate length downstream for arcs
    first = True
    # Iterate over upsteram node ids starting from the first one
    # which represents downstream node of the outlet arc
    for nodeId in sorted(myNetwork.keys()):
        f = layer.getFeatures(request.setFilterFid(myNetwork[nodeId])).next()
        # for outlet arc downstream length set to zero
        if first:
            provider.changeAttributeValues({myNetwork[nodeId]:{idxLenDown:0.0}})
            first = False
            continue

        arcLen = f['Length']
        downArcId = f['DownArcId']
        f = layer.getFeatures(request.setFilterFid(downArcId)).next()
        lenDown = f['LengthDown'] if f['LengthDown'] else 0.0
        provider.changeAttributeValues({myNetwork[nodeId]:{idxLenDown: arcLen + lenDown}})

    # calculate Strahler orders
    # Iterate over upsteram node ids starting from the last ones
    # which represents source arcs
    for nodeId in sorted(myNetwork.keys(), reverse=True):
        f = layer.getFeatures(request.setFilterFid(myNetwork[nodeId])).next()
        fid = f.id()
        upstreamArcs = f['UpArcId']
        if not upstreamArcs:
            provider.changeAttributeValues({fid:{idxStrahler: 1}})
        else:
            orders = []
            for i in upstreamArcs.split(','):
                f = layer.getFeatures(request.setFilterFid(int(i))).next()
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

    # Calculate order frequency
    maxOrder = int(layer.maximumValue(idxStrahler))
    ordersFrequency = dict()
    bifRatios = dict()
    # Initialize dictionaries
    for i in xrange(1, maxOrder + 1):
        ordersFrequency[i] = dict(N=0.0, Ndu=0.0, Na=0.0)
        bifRatios[i] = dict(Rbu=0.0, Rbdu=0.0, Ru=0.0)

    for i in xrange(1, maxOrder + 1):
        ordersFrequency[i] = dict(N=0.0, Ndu=0.0, Na=0.0)
        bifRatios[i] = dict(Rbu=0.0, Rbdu=0.0, Ru=0.0)

    for i in xrange(1, maxOrder + 1):
        request.setFilterExpression('"StrahOrder" = %s' % i)
        for f in layer.getFeatures(request):
            order = int(f['StrahOrder'])
            upstreamArcs = f['UpArcId'].split(',') if f['UpArcId'] else []
            if len(upstreamArcs) == 0:
                ordersFrequency[i]['N'] += 1.0
            elif len(upstreamArcs) > 1:
                ordersFrequency[order]['N'] += 1.0
                for j in upstreamArcs:
                    f = layer.getFeatures(QgsFeatureRequest().setFilterFid(int(j))).next()
                    upOrder = int(f['StrahOrder'])
                    diff = upOrder - order
                    if diff == 1:
                        ordersFrequency[upOrder]['Ndu'] += 1.0
                    if diff > 1:
                        ordersFrequency[upOrder]['Na'] += 1.0

    segFr = open('segfr.csv', 'wb')
    bifRat = open('bifrat.csv', 'wb')
    segFrWriter = csv.writer(segFr)
    segFrWriter.writerow(['order', 'N', 'NDU', 'NA'])
    bifRatWriter = csv.writer(bifRat)
    bifRatWriter.writerow(['order', 'RBD', 'RB', 'RU'])

    # Calculate bifurcation parameters
    for k, v in ordersFrequency.iteritems():
        if k != maxOrder:
            bifRatios[k]['Rbu'] = ordersFrequency[k]['N'] / ordersFrequency[k + 1]['N']
            bifRatios[k]['Rbdu'] = ordersFrequency[k]['Ndu'] / ordersFrequency[k + 1]['N']
        else:
            bifRatios[k]['Rbu'] = 0.0
            bifRatios[k]['Rbdu'] = 0.0

        bifRatios[k]['Ru'] = bifRatios[k]['Rbu'] - bifRatios[k]['Rbdu']

        segFrWriter.writerow([k, v['N'], v['Ndu'], v['Na']])
        bifRatWriter.writerow([k, bifRatios[k]['Rbdu'], bifRatios[k]['Rbu'], bifRatios[k]['Ru']])

    segFr.close()
    bifRat.close()

    QgsApplication.exitQgis()
