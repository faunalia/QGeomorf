# -*- coding: utf-8 -*-

import os
import subprocess

from PyQt4.QtCore import QCoreApplication

from processing.core.ProcessingConfig import ProcessingConfig
from processing.core.ProcessingLog import ProcessingLog


class GeomorfUtils:

    GEOMORF_FOLDER = 'GEOMORF_FOLDER'
    MPIEXEC_FOLDER = 'MPIEXEC_FOLDER'
    MPI_PROCESSES = 'MPI_PROCESSES'

    @staticmethod
    def geomorfPath():
        folder = ProcessingConfig.getSetting(GeomorfUtils.GEOMORF_FOLDER)
        if folder is None:
            folder = ''

        return folder

    @staticmethod
    def mpiexecPath():
        folder = ProcessingConfig.getSetting(GeomorfUtils.MPIEXEC_FOLDER)
        if folder is None:
            folder = ''

        return folder

    @staticmethod
    def execute(command, progress):
        loglines = []
        fused_command = ''.join(['%s ' % c for c in command])
        progress.setCommand(fused_command.replace('" "', ' ').strip('"'))
        proc = subprocess.Popen(
            fused_command,
            shell=True,
            stdout=subprocess.PIPE,
            stdin=open(os.devnull),
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        ).stdout
        for line in iter(proc.readline, ''):
            progress.setConsoleInfo(line)
            loglines.append(line)
        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, loglines)
