from PyQt4.QtCore import QVariant

from qgis.core import (QgsGeometry, QgsVectorLayer, QgsFeature, QgsFields,
    QgsField)


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


def makeDictionary(layer):
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


def findNode(layer, node):
    for f in layer.getFeatures():
        if f.geometry().asPoint() == node:
            return f.id()

    return -1
