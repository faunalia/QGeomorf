# -*- coding: utf-8 -*-

import os

from PyQt4.QtGui import QIcon

from processing.core.AlgorithmProvider import AlgorithmProvider
from processing.core.ProcessingConfig import Setting, ProcessingConfig

from QGeomorf.Geomorf import Geomorf
from QGeomorf.GeomorfUtils import GeomorfUtils


pluginPath = os.path.dirname(__file__)


class QGeomorfProvider(AlgorithmProvider):

    def __init__(self):
        AlgorithmProvider.__init__(self)

        self.activate = True

        self.alglist = [Geomorf()]
        for alg in self.alglist:
            alg.provider = self

    def initializeSettings(self):
        AlgorithmProvider.initializeSettings(self)

        ProcessingConfig.addSetting(Setting(self.getDescription(),
            GeomorfUtils.GEOMORF_FOLDER,
            self.tr('Geomorf command line tool folder'),
            GeomorfUtils.geomorfPath()))
        ProcessingConfig.addSetting(Setting(self.getDescription(),
            GeomorfUtils.MPIEXEC_FOLDER,
            self.tr('MPICH2/OpenMPI bin directory'),
            GeomorfUtils.mpiexecPath()))
        ProcessingConfig.addSetting(Setting(self.getDescription(),
            GeomorfUtils.MPI_PROCESSES,
            self.tr('Number of MPI parallel processes to use'), 2))

    def unload(self):
        AlgorithmProvider.unload(self)

        ProcessingConfig.removeSetting(GeomorfUtils.GEOMORF_FOLDER)
        ProcessingConfig.removeSetting(GeomorfUtils.MPIEXEC_FOLDER)
        ProcessingConfig.removeSetting(GeomorfUtils.MPI_PROCESSES)

    def getName(self):
        return 'QGeomorf'

    def getDescription(self):
        return 'QGeomorf'

    def getIcon(self):
        return QIcon(os.path.join(pluginPath, 'icons', 'enea.png'))

    def _loadAlgorithms(self):
        self.algs = self.alglist
