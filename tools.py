from PyQt4.QtCore import QVariant

from qgis.core import (QgsGeometry, QgsVectorLayer, QgsFeature, QgsFields,
    QgsField)

from processing.tools import vector


def makePoints(layer):
    authId = layer.crs().authid()
    nodes = QgsVectorLayer(
        'Point?crs={}'.format(authId), 'network_nodes', 'memory')

    fields = QgsFields()
    fields.append(QgsField('id', QVariant.Int, '', 10))
    fields.append(QgsField('downNodeId', QVariant.Int, '', 10))
    fields.append(QgsField('upNodeId', QVariant.Int, '', 10))

    provider = nodes.dataProvider()
    provider.addAttributes(fields.toList())
    nodes.updateFields()

    idx = 0
    points = []
    ft = QgsFeature()
    ft.setFields(fields)

    for f in layer.getFeatures():
        arc = f.geometry().asPolyline()
        if arc[0] not in points:
            ft.setGeometry(QgsGeometry.fromPoint(arc[0]))
            ft['id'] = idx
            provider.addFeatures([ft])
            points.append(arc[0])
            idx += 1

        if arc[-1] not in points:
            ft.setGeometry(QgsGeometry.fromPoint(arc[-1]))
            ft['id'] = idx
            provider.addFeatures([ft])
            points.append(arc[-1])
            idx += 1

    return nodes


def arcsAadjacencyDictionary(layer):
    '''Build arc adjacency dictionary for the input stream network layer.

    This dictionary is a set of adjacency lists compiled for each node in
    th network.
    '''
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


def makeHelperDictionaries(layer):
    # Mapping between upstream node id from attribute table and  QGIS
    # feature id. Will be used to sort features from the network table

    myNetwork = dict()

    # Find upstream and downstream arc ids for each arc in the stream
    # network layer. First we generate helper arcPerNodeId dictionary
    # with node ids as keys and lists of arc ids connected to this node
    # as values
    # Algorithm at pages 55-56 "Automated AGQ4Vector Watershed.pdf"
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

    return myNetwork, arcsPerNodeId


def findOrCreateField(layer, fieldList, fieldName, fieldType=QVariant.Double,
        fieldLen=24, fieldPrec=15):
    idx = layer.fieldNameIndex(fieldName)
    if idx == -1:
        fn = vector.createUniqueFieldName(fieldName, fieldList)
        field = QgsField(fn, fieldType, '', fieldLen, fieldPrec)
        idx = len(fieldList)
        fieldList.append(field)

    return (idx, fieldList)


def findField(layer, fieldName):
    idx = layer.fieldNameIndex(fieldName)
    return idx
