from qgis.core import QgsGeometry


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
