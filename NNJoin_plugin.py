# -*- coding: utf-8 -*-
"""
/***************************************************************************
 NNJoin
                                 A QGIS plugin
 Nearest neighbour spatial join
                              -------------------
        begin                : 2014-09-04
        git sha              : $Format:%H$
        copyright            : (C) 2014 by Håvard Tveite; Xiaowei Zeng
        email                : havard.tveite@nmbu.no; xiaowei.zeng@cug.edu.cn
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os.path
# QGIS imports
from qgis.core import QgsProject, QgsMapLayer
# from qgis.core import QgsMapLayerRegistry, QgsMapLayer
# from qgis.core import QGis
from qgis.core import QgsWkbTypes
from qgis.core import QgsMessageLog, Qgis

# import processing

# QGIS 3
from qgis.PyQt.QtCore import QSettings, QCoreApplication, QTranslator
from qgis.PyQt.QtCore import qVersion
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtGui import QIcon

# QGIS 2
# from PyQt4.QtCore import QSettings, QCoreApplication, QTranslator, qVersion
# from PyQt4.QtGui import QAction, QMessageBox, QIcon

# Plugin imports
from .resources import *
from .NNJoin_gui import NNJoinDialog


class NNJoin(object):
    """QGIS NNJoin Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save a reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'NNJoin_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.NNJOIN = self.tr('NNJoin')
        self.NNJOINAMP = self.tr('&NNJoin')
        self.toolbar = None
        # Separate toolbar for NNJoin:
        # self.toolbar = self.iface.addToolBar(self.NNJOIN)
        # self.toolbar.setObjectName(self.NNJOIN)

        # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('NNJoin', message)

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI"""
        icon_path = os.path.join(os.path.dirname(__file__), "nnjoin.png")
        # Create action that will start plugin configuration
        self.nnj_action = QAction(
            QIcon(icon_path),
            self.NNJOIN, self.iface.mainWindow())
        # connect the action to the run method
        self.nnj_action.triggered.connect(self.run)
        # Add toolbar button
        if hasattr(self.iface, 'addVectorToolBarIcon'):
            self.iface.addVectorToolBarIcon(self.nnj_action)
        else:
            self.iface.addToolBarIcon(self.nnj_action)
        # Add menu item
        if hasattr(self.iface, 'addPluginToVectorMenu'):
            self.iface.addPluginToVectorMenu(self.NNJOINAMP, self.nnj_action)
        else:
            self.iface.addPluginToMenu(self.NNJOINAMP, self.nnj_action)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI"""
        # Remove the plugin menu item
        if hasattr(self.iface, 'removePluginVectorMenu'):
            self.iface.removePluginVectorMenu(self.NNJOINAMP, self.nnj_action)
        else:
            self.iface.removePluginMenu(self.NNJOINAMP, self.nnj_action)
        # Remove the plugin toolbar icon
        if hasattr(self.iface, 'removeVectorToolBarIcon'):
            self.iface.removeVectorToolBarIcon(self.nnj_action)
        else:
            self.iface.removeToolBarIcon(self.nnj_action)

    def run(self):
        """Run method that initialises and starts the user interface"""
        # Ensure QMessageBox is available in this scope
        from qgis.PyQt.QtWidgets import QMessageBox
        
        try:
            # Log some information before creating the dialog
            QgsMessageLog.logMessage("Starting NNJoin plugin", "NNJoin", Qgis.Info)
            
            # Create dialog
            self.dlg = NNJoinDialog(self.iface)
            
            # Initialize components
            self.dlg.progressBar.setValue(0)
            self.dlg.outputDataset.setText('Result')
            
            # Prepare layer list
            layers = QgsProject.instance().mapLayers()
            layerslist = []
            
            # Collect valid vector layers
            for id in layers.keys():
                if layers[id].type() == QgsMapLayer.VectorLayer:
                    if not layers[id].isValid():
                        QgsMessageLog.logMessage('Layer ' + layers[id].name() + ' is not valid', 
                                              "NNJoin", Qgis.Warning)
                    if layers[id].wkbType() != QgsWkbTypes.NoGeometry:
                        layerslist.append((layers[id].name(), id))
            
            # Check if there are available layers
            if len(layerslist) == 0 or len(layers) == 0:
                QMessageBox.information(None,
                   self.tr('Information'),
                   self.tr('Vector layers not found'))
                return
            
            # Populate layer dropdown lists
            self.dlg.inputVectorLayer.clear()
            for layerdescription in layerslist:
                self.dlg.inputVectorLayer.addItem(layerdescription[0],
                                            layerdescription[1])
            
            self.dlg.joinVectorLayer.clear()
            for layerdescription in layerslist:
                self.dlg.joinVectorLayer.addItem(layerdescription[0],
                                            layerdescription[1])
            
            # Show dialog in modal mode instead of non-modal + exec_()
            self.dlg.setModal(True)
            self.dlg.show()
            
        except Exception as e:
            # Catch and log any exceptions to avoid QGIS crash
            import traceback
            error_msg = "NNJoin plugin error: " + traceback.format_exc()
            QgsMessageLog.logMessage(error_msg, "NNJoin", Qgis.Critical)
            # Try to show error message to user
            try:
                QMessageBox.critical(None, "NNJoin Error", 
                                   "An error occurred in the NNJoin plugin. See the QGIS log for details.")
            except:
                pass
