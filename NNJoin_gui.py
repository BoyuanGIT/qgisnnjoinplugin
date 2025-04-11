# -*- coding: utf-8 -*-
"""
/***************************************************************************
 NN_Join_gui
                      GUI of the NNJoin plugin

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

from os.path import dirname
from os.path import join

from qgis.core import QgsMessageLog, QgsProject, Qgis
from qgis.core import QgsMapLayer
from qgis.core import QgsWkbTypes
from qgis.gui import QgsMessageBar
# from qgis.utils import showPluginHelp

# QGIS 3
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QObject, QThread, Qt
from qgis.PyQt.QtCore import QCoreApplication, QUrl
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox
from qgis.PyQt.QtWidgets import QProgressBar, QPushButton
from qgis.PyQt.QtGui import QDesktopServices

from .NNJoin_engine import Worker

FORM_CLASS, _ = uic.loadUiType(join(
    dirname(__file__), 'ui_frmNNJoin.ui'))


class NNJoinDialog(QDialog, FORM_CLASS):
    def __init__(self, iface, parent=None):
        """Constructor."""
        # Basic settings
        self.iface = iface
        self.plugin_dir = dirname(__file__)
        
        # Localized text
        self.NNJOIN = self.tr('NNJoin')
        self.CANCEL = self.tr('Cancel')
        self.CLOSE = self.tr('Close')
        self.HELP = self.tr('Help')
        self.OK = self.tr('OK')
        
        # Call parent constructor before creating UI
        QDialog.__init__(self, parent)
        
        # Set simple window flags to avoid using complex Qt features
        self.setWindowFlags(Qt.Window)
        
        # Now set up UI
        self.setupUi(self)
        
        # Simplify UI component configuration, avoid using complex styles
        okButton = self.button_box.button(QDialogButtonBox.Ok)
        okButton.setText(self.OK)
        self.cancelButton = self.button_box.button(QDialogButtonBox.Cancel)
        self.cancelButton.setText(self.CANCEL)
        closeButton = self.button_box.button(QDialogButtonBox.Close)
        closeButton.setText(self.CLOSE)
        
        # Use simple checked/unchecked settings
        self.approximate_input_geom_cb.setChecked(False)  
        self.approximate_input_geom_cb.setVisible(False)
        
        # Avoid using custom stylesheets
        self.use_indexapprox_cb.setChecked(False)
        self.use_indexapprox_cb.setVisible(False)
        
        self.use_index_nonpoint_cb.setChecked(False)
        self.use_index_nonpoint_cb.setVisible(False)
        
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)
        self.button_box.button(QDialogButtonBox.Cancel).setEnabled(False)
        
        # Help button
        helpButton = self.helpButton
        helpButton.setText(self.HELP)

        # Simplify signal connections
        okButton.clicked.connect(self.simplifiedStartWorker)
        closeButton.clicked.connect(self.reject)  # Use standard Qt dialog close
        helpButton.clicked.connect(self.help)
        
        # Simplify other connections
        self.approximate_input_geom_cb.stateChanged.connect(self.useindexchanged)
        self.use_indexapprox_cb.stateChanged.connect(self.useindexchanged)
        self.use_index_nonpoint_cb.stateChanged.connect(self.useindexchanged)
        
        self.inputVectorLayer.currentIndexChanged.connect(self.layerchanged)
        self.joinVectorLayer.currentIndexChanged.connect(self.joinlayerchanged)
        self.distancefieldname.textChanged.connect(self.distfieldchanged)
        self.joinPrefix.editingFinished.connect(self.fieldchanged)
        
        # Simplify layer list change handling
        theRegistry = QgsProject.instance()
        theRegistry.layersAdded.connect(self.layerlistchanged)
        theRegistry.layersRemoved.connect(self.layerlistchanged)
        
        # Instance variables
        self.mem_layer = None
        self.worker = None
        self.mythread = None
        self.progressDialog = None
        self.inputlayerid = None
        self.joinlayerid = None
        self.layerlistchanging = False
    
    def simplifiedStartWorker(self):
        """Simplified worker startup method, avoid using message bar and complex thread management"""
        try:
            # First clean up any existing resources
            self.cleanupResources()
            
            # Basic checks
            layerindex = self.inputVectorLayer.currentIndex()
            layerId = self.inputVectorLayer.itemData(layerindex)
            inputlayer = QgsProject.instance().mapLayer(layerId)
            if inputlayer is None:
                self.simplifiedShowError(self.tr('No input layer defined'))
                return
                
            joinindex = self.joinVectorLayer.currentIndex()
            joinlayerId = self.joinVectorLayer.itemData(joinindex)
            joinlayer = QgsProject.instance().mapLayer(joinlayerId)
            if joinlayer is None:
                self.simplifiedShowError(self.tr('No join layer defined'))
                return
                
            if joinlayer is not None and joinlayer.crs().isGeographic():
                self.simplifiedShowWarning('Geographic CRS used for the join layer -'
                                 ' distances will be in decimal degrees!')
                
            # Collect parameters
            outputlayername = self.outputDataset.text()
            approximateinputgeom = self.approximate_input_geom_cb.isChecked()
            joinprefix = self.joinPrefix.text()
            useindex = self.use_index_nonpoint_cb.isChecked()
            useindexapproximation = self.use_indexapprox_cb.isChecked()
            distancefieldname = self.distancefieldname.text()
            selectedinputonly = self.inputSelected.isChecked()
            selectedjoinonly = self.joinSelected.isChecked()
            excludecontaining = self.exclude_containing_poly_cb.isChecked()
            
            # Use QProgressDialog instead of message bar
            from qgis.PyQt.QtWidgets import QProgressDialog
            self.progressDialog = QProgressDialog(self.tr("Processing join..."), self.tr("Cancel"), 0, 100, self)
            self.progressDialog.setWindowTitle(self.tr("NNJoin"))
            self.progressDialog.setWindowModality(Qt.WindowModal)
            self.progressDialog.setMinimumDuration(0)  # Show immediately
            
            # Create worker object
            self.worker = Worker(inputlayer, joinlayer, outputlayername,
                            joinprefix, distancefieldname,
                            approximateinputgeom, useindexapproximation,
                            useindex, selectedinputonly, selectedjoinonly,
                            excludecontaining)
                            
            # Create thread
            self.mythread = QThread()
            
            # Connect signals
            self.worker.status.connect(lambda msg: QgsMessageLog.logMessage(msg, self.NNJOIN, Qgis.Info))
            self.worker.progress.connect(self.progressDialog.setValue)
            self.worker.finished.connect(lambda ok, ret: self.simplifiedWorkerFinished(ok, ret))
            self.worker.error.connect(lambda msg: self.simplifiedShowError(msg))
            
            # Connect cancel button
            self.progressDialog.canceled.connect(self.worker.kill)
            
            # Install to thread
            self.worker.moveToThread(self.mythread)
            self.mythread.started.connect(self.worker.run)
            
            # Update UI state
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)
            self.button_box.button(QDialogButtonBox.Close).setEnabled(False)
            self.button_box.button(QDialogButtonBox.Cancel).setEnabled(True)
            
            # Show progress dialog
            self.progressDialog.show()
            
            # Start thread
            self.mythread.start()
            
            if layerId == joinlayerId:
                self.simplifiedShowInfo("The join layer is the same as the"
                                " input layer - doing a self join!")
                
        except Exception as e:
            import traceback
            self.simplifiedShowError("Error: " + traceback.format_exc())
            self.cleanupResources()
    
    def simplifiedWorkerFinished(self, ok, ret):
        """Simplified worker completion handling"""
        try:
            # Close progress dialog
            if self.progressDialog is not None:
                self.progressDialog.close()
                self.progressDialog = None
            
            # Process result
            if ok and ret is not None:
                # Add result layer
                mem_layer = ret
                QgsMessageLog.logMessage(self.tr('NNJoin finished'), self.NNJOIN, Qgis.Info)
                
                try:
                    mem_layer.dataProvider().updateExtents()
                    mem_layer.commitChanges()
                    self.layerlistchanging = True
                    QgsProject.instance().addMapLayer(mem_layer)
                    self.layerlistchanging = False
                except Exception as e:
                    import traceback
                    self.simplifiedShowError("Error adding result layer: " + traceback.format_exc())
            else:
                if not ok:
                    self.simplifiedShowError(self.tr('Aborted') + '!')
                else:
                    self.simplifiedShowError(self.tr('No layer created') + '!')
            
            # Update UI state
            self.progressBar.setValue(0)
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)
            self.button_box.button(QDialogButtonBox.Close).setEnabled(True)
            self.button_box.button(QDialogButtonBox.Cancel).setEnabled(False)
                    
        except Exception as e:
            import traceback
            QgsMessageLog.logMessage("Error in simplifiedWorkerFinished: " + traceback.format_exc(),
                                    self.NNJOIN, Qgis.Critical)
        finally:
            # Clean up thread and worker
            self.cleanupResources()
    
    def cleanupResources(self):
        """Clean up threads and other resources"""
        try:
            # Close progress dialog
            if hasattr(self, 'progressDialog') and self.progressDialog is not None:
                try:
                    self.progressDialog.close()
                except:
                    pass
                self.progressDialog = None
            
            # Clean up worker object
            if hasattr(self, 'worker') and self.worker is not None:
                try:
                    # Mark for termination
                    self.worker.abort = True
                    # Clean up references
                    self.worker.deleteLater()
                except:
                    pass
                self.worker = None
            
            # Clean up thread
            if hasattr(self, 'mythread') and self.mythread is not None:
                try:
                    # If thread is still running, try to stop it
                    if self.mythread.isRunning():
                        self.mythread.quit()
                        # Wait briefly for thread to end
                        self.mythread.wait(500)
                    
                    # Delete thread
                    self.mythread.deleteLater()
                except:
                    pass
                self.mythread = None
        except Exception as e:
            import traceback
            QgsMessageLog.logMessage("Error in cleanupResources: " + traceback.format_exc(),
                                  self.NNJOIN, Qgis.Warning)
    
    def closeEvent(self, event):
        """Override close event to ensure safe cleanup"""
        self.cleanupResources()
        super(NNJoinDialog, self).closeEvent(event)
    
    def reject(self):
        """Override reject method to ensure safe cleanup"""
        self.cleanupResources()
        super(NNJoinDialog, self).reject()
    
    def accept(self):
        """Override accept method to ensure safe cleanup"""
        self.cleanupResources()
        super(NNJoinDialog, self).accept()
    
    def simplifiedShowError(self, text):
        """Simplified error display using standard dialog instead of message bar"""
        QgsMessageLog.logMessage('Error: ' + text, self.NNJOIN, Qgis.Critical)
        # Use standard Qt message box
        from qgis.PyQt.QtWidgets import QMessageBox
        QMessageBox.critical(None, self.tr('Error'), text)
    
    def simplifiedShowWarning(self, text):
        """Simplified warning display using only log"""
        QgsMessageLog.logMessage('Warning: ' + text, self.NNJOIN, Qgis.Warning)
    
    def simplifiedShowInfo(self, text):
        """Simplified info display using only log"""
        QgsMessageLog.logMessage('Info: ' + text, self.NNJOIN, Qgis.Info)

    def fieldchanged(self, number=0):
        # If the layer list is being updated, don't do anything
        if self.layerlistchanging:
            return
        self.updateui()
        # End of fieldchanged

    def distfieldchanged(self, number=0):
        # If the layer list is being updated, don't do anything
        # if self.layerlistchanging:
        #     return

        # Retrieve the input layer
        layerindex = self.inputVectorLayer.currentIndex()
        layerId = self.inputVectorLayer.itemData(layerindex)
        inputlayer = QgsProject.instance().mapLayer(layerId)
        # Retrieve the join layer
        joinindex = self.joinVectorLayer.currentIndex()
        joinlayerId = self.joinVectorLayer.itemData(joinindex)
        joinlayer = QgsProject.instance().mapLayer(joinlayerId)
        # Enable the OK button (if layers are OK)
        if inputlayer is not None and joinlayer is not None:
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)
        if inputlayer is not None:
            # Set the default background (white) for the distance field name
            self.distancefieldname.setStyleSheet("background:#fff;")
            # Check if the distance field name already is used
            inputfields = inputlayer.fields().toList()
            for infield in inputfields:
                if infield.name() == self.distancefieldname.text():
                    self.distancefieldname.setStyleSheet("background:#f00;")
                    self.showInfo(
                           "Distance field name conflict in input layer")
                    if self.button_box.button(
                                         QDialogButtonBox.Ok).isEnabled():
                        self.button_box.button(
                                   QDialogButtonBox.Ok).setEnabled(False)
            if joinlayer is not None:
                joinfields = joinlayer.fields().toList()
                for joinfield in joinfields:
                    if (self.joinPrefix.text() + joinfield.name() ==
                                           self.distancefieldname.text()):
                        self.distancefieldname.setStyleSheet(
                                                       "background:#f00;")
                        self.showInfo(
                             "Distance field name conflict in join layer")
                        if self.button_box.button(
                                          QDialogButtonBox.Ok).isEnabled():
                            self.button_box.button(
                                    QDialogButtonBox.Ok).setEnabled(False)
        # self.updateui()
        # End of distfieldchanged

    def joinlayerchanged(self, number=0):
        # If the layer list is being updated, don't do anything
        if self.layerlistchanging:
            return
        # Retrieve the join layer
        joinindex = self.joinVectorLayer.currentIndex()
        joinlayerId = self.joinVectorLayer.itemData(joinindex)
        self.joinlayerid = joinlayerId
        joinlayer = QgsProject.instance().mapLayer(joinlayerId)
        # Geographic? - give a warning!
        if joinlayer is not None and joinlayer.crs().isGeographic():
            self.showWarning('Geographic CRS used for the join layer -'
                             ' distances will be in decimal degrees!')
        self.layerchanged()
        # End of joinlayerchanged

    def layerchanged(self, number=0):
        """Do the necessary updates after a layer selection has
           been changed."""
        # If the layer list is being updated, don't do anything
        if self.layerlistchanging:
            return
        # Retrieve the input layer
        layerindex = self.inputVectorLayer.currentIndex()
        layerId = self.inputVectorLayer.itemData(layerindex)
        self.inputlayerid = layerId
        inputlayer = QgsProject.instance().mapLayer(layerId)
        # Retrieve the join layer
        joinindex = self.joinVectorLayer.currentIndex()
        joinlayerId = self.joinVectorLayer.itemData(joinindex)
        self.joinlayerid = joinlayerId
        joinlayer = QgsProject.instance().mapLayer(joinlayerId)
        # Update the input layer UI label with input geometry
        # type information
        if inputlayer is not None:
            inputwkbtype = inputlayer.wkbType()
            # inputlayerwkbtext = self.getwkbtext(inputwkbtype)
            inputlayerwkbtext = QgsWkbTypes.displayString(inputwkbtype)
            self.inputgeometrytypelabel.setText(inputlayerwkbtext)
        # Update the join layer UI label with join geometry type
        # information
        if joinlayer is not None:
            joinwkbtype = joinlayer.wkbType()
            #joinlayerwkbtext = self.getwkbtext(joinwkbtype)
            joinlayerwkbtext = QgsWkbTypes.displayString(joinwkbtype)
            self.joingeometrytypelabel.setText(joinlayerwkbtext)
        # Check the coordinate systems
        # Different CRSs? - give a warning!
        if (inputlayer is not None and joinlayer is not None and
                inputlayer.crs() != joinlayer.crs()):
            self.showWarning(
                  'Layers have different CRS! - Input CRS authid: ' +
                  str(inputlayer.crs().authid()) +
                  ' - Join CRS authid: ' +
                  str(joinlayer.crs().authid()) +
                  ".  The input layer will be transformed.")
        self.updateui()
        # end of layerchanged

    def useindexchanged(self, number=0):
        self.updateui()

    def layerlistchanged(self):
        # When a layer has been added to or removed by the user,
        # the comboboxes should be updated to include the new
        # possibilities.
        self.layerlistchanging = True
        # Repopulate the input and join layer combo boxes
        # Save the currently selected input layer
        inputlayerid = self.inputlayerid
        layers = QgsProject.instance().mapLayers()
        layerslist = []
        for id in layers.keys():
            if layers[id].type() == QgsMapLayer.VectorLayer:
                if not layers[id].isValid():
                    QMessageBox.information(None,
                        self.tr('Information'),
                        'Layer ' + layers[id].name() + ' is not valid')
                if layers[id].wkbType() != QgsWkbTypes.NoGeometry:
                    layerslist.append((layers[id].name(), id))
        # Add the layers to the input layers combobox
        self.inputVectorLayer.clear()
        for layerdescription in layerslist:
            self.inputVectorLayer.addItem(layerdescription[0],
                                        layerdescription[1])
        # Set the previous selection for the input layer
        for i in range(self.inputVectorLayer.count()):
            if self.inputVectorLayer.itemData(i) == inputlayerid:
                self.inputVectorLayer.setCurrentIndex(i)
        # Save the currently selected join layer
        joinlayerid = self.joinlayerid
        # Add the layers to the join layers combobox
        self.joinVectorLayer.clear()
        for layerdescription in layerslist:
            self.joinVectorLayer.addItem(layerdescription[0],
                                        layerdescription[1])
        # Set the previous selection for the join layer
        for i in range(self.joinVectorLayer.count()):
            if self.joinVectorLayer.itemData(i) == joinlayerid:
                self.joinVectorLayer.setCurrentIndex(i)
        self.layerlistchanging = False
        self.updateui()
        # End of layerlistchanged

    def updateui(self):
        """Do the necessary updates after a layer selection has
           been changed."""
        # if self.layerlistchanged:
        #     return
        # Update the output dataset name
        self.outputDataset.setText(self.inputVectorLayer.currentText() +
                                   '_' + self.joinVectorLayer.currentText())
        # Retrieve the input layer
        layerindex = self.inputVectorLayer.currentIndex()
        layerId = self.inputVectorLayer.itemData(layerindex)
        inputlayer = QgsProject.instance().mapLayer(layerId)
        # Retrieve the join layer
        joinindex = self.joinVectorLayer.currentIndex()
        joinlayerId = self.joinVectorLayer.itemData(joinindex)
        joinlayer = QgsProject.instance().mapLayer(joinlayerId)
        # Enable the OK button (if layers are OK)
        if inputlayer is not None and joinlayer is not None:
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)
        # Check the geometry type of the input layer and set
        # user interface options accordingly
        if inputlayer is not None:
            wkbType = inputlayer.wkbType()
            geomType = inputlayer.geometryType()  # not used yet
            joinwkbType = QgsWkbTypes.Unknown
            joingeomType = QgsWkbTypes.UnknownGeometry  # not used yet
            if joinlayer is not None:
                joinwkbType = joinlayer.wkbType()
                joingeomType = joinlayer.geometryType()
            # If the input layer is not a point layer, allow choosing
            # approximate geometry (centroid)
            if wkbType == QgsWkbTypes.Point or wkbType == QgsWkbTypes.Point25D:
                # Input layer is a simple point layer and can not
                # be approximated
                self.approximate_input_geom_cb.blockSignals(True)
                self.approximate_input_geom_cb.setCheckState(Qt.Unchecked)
                self.approximate_input_geom_cb.setVisible(False)
                self.approximate_input_geom_cb.blockSignals(False)
            else:
                # Input layer is not a point layer, so approximation
                # is possible
                self.approximate_input_geom_cb.blockSignals(True)
                self.approximate_input_geom_cb.setVisible(True)
                self.approximate_input_geom_cb.blockSignals(False)
            # Update the use index checkbox
            if ((wkbType == QgsWkbTypes.LineString or
                    wkbType == QgsWkbTypes.LineString25D or
                    wkbType == QgsWkbTypes.Polygon or
                    wkbType == QgsWkbTypes.Polygon25D) and
                    not self.approximate_input_geom_cb.isChecked()):
                # The input layer is a line or polygong layer that
                # is not approximated, so the user is allowed to
                # choose not to use the spatial index (not very useful!)
                if not self.use_index_nonpoint_cb.isVisible():
                    self.use_index_nonpoint_cb.blockSignals(True)
                    self.use_index_nonpoint_cb.setCheckState(Qt.Checked)
                    self.use_index_nonpoint_cb.setVisible(True)
                    self.use_index_nonpoint_cb.blockSignals(False)
            else:
                # The input layer is either a point approximation
                # or it is a point layer (or some kind of
                # multigeometry!), anyway we won't allow the user to
                # choose not to use a spatial index
                self.use_index_nonpoint_cb.blockSignals(True)
                self.use_index_nonpoint_cb.setCheckState(Qt.Unchecked)
                self.use_index_nonpoint_cb.setVisible(False)
                self.use_index_nonpoint_cb.blockSignals(False)
            # This does not work!!????
            # Update the use index approximation checkbox:
            if (((wkbType == QgsWkbTypes.Point) or
                 (wkbType == QgsWkbTypes.Point25D) or
                 self.approximate_input_geom_cb.isChecked()) and
                not (joinwkbType == QgsWkbTypes.Point or
                         joinwkbType == QgsWkbTypes.Point25D)):
                # For non-point join layers and point input layers,
                # the user is allowed to choose an approximation (the
                # index geometry) to be used for the join geometry in
                # the join.
                self.use_indexapprox_cb.setVisible(True)
            else:
                # For point join layers, and non-point,
                # non-point-approximated input layers, the user is
                # not allowed to choose an approximation (the index
                # geometry) to be used for the join geometry in the
                # join.
                self.use_indexapprox_cb.blockSignals(True)
                self.use_indexapprox_cb.setCheckState(Qt.Unchecked)
                self.use_indexapprox_cb.setVisible(False)
                self.use_indexapprox_cb.blockSignals(False)

            # Update the exclude containing polygon checkbox:
            if ((wkbType == QgsWkbTypes.Point or
                 wkbType == QgsWkbTypes.Point25D or
                 self.approximate_input_geom_cb.isChecked()) and
                (joinwkbType == QgsWkbTypes.Polygon or
                 joinwkbType == QgsWkbTypes.Polygon25D) and
                (not self.use_indexapprox_cb.isChecked())):
                # For polygon join layers and point input layers,
                # the user is allowed to choose to exclude the
                # containing polygon in the join.
                self.exclude_containing_poly_cb.blockSignals(True)
                self.exclude_containing_poly_cb.setVisible(True)
                self.exclude_containing_poly_cb.blockSignals(False)
            else:
                self.exclude_containing_poly_cb.blockSignals(True)
                self.exclude_containing_poly_cb.setCheckState(Qt.Unchecked)
                self.exclude_containing_poly_cb.setVisible(False)
                self.exclude_containing_poly_cb.blockSignals(False)

            # Set the default background (white) for the distance field name
            self.distancefieldname.setStyleSheet("background:#fff;")
            # Check if the distance field name already is used
            inputfields = inputlayer.fields().toList()
            for infield in inputfields:
                if infield.name() == self.distancefieldname.text():
                    self.distancefieldname.setStyleSheet("background:#f00;")
                    self.showInfo(
                           "Distance field name conflict in input layer")
                    if self.button_box.button(
                                         QDialogButtonBox.Ok).isEnabled():
                        self.button_box.button(
                                   QDialogButtonBox.Ok).setEnabled(False)
                    break
            if joinlayer is not None:
                joinfields = joinlayer.fields().toList()
                for joinfield in joinfields:
                    if (self.joinPrefix.text() + joinfield.name() ==
                                           self.distancefieldname.text()):
                        self.distancefieldname.setStyleSheet(
                                                       "background:#f00;")
                        self.showInfo(
                             "Distance field name conflict in join layer")
                        if self.button_box.button(
                                          QDialogButtonBox.Ok).isEnabled():
                            self.button_box.button(
                                    QDialogButtonBox.Ok).setEnabled(False)
                        break
        else:
            # No input layer defined, so options are disabled
            self.approximate_input_geom_cb.setVisible(False)
            self.use_indexapprox_cb.setVisible(False)
            self.use_index_nonpoint_cb.setVisible(False)
        # End of updateui

    def getwkbtext(self, number):
        if number == QgsWkbTypes.Unknown:
            return "Unknown"
        elif number == QgsWkbTypes.Point:
            return "Point"
        elif number == QgsWkbTypes.PointZ:
            self.showWarning('The Z coordinate will be ignored for PointZ layers')
            return "PointZ"
        elif number == QgsWkbTypes.LineString:
            return "LineString"
        elif number == QgsWkbTypes.Polygon:
            return "Polygon"
        elif number == QgsWkbTypes.MultiPoint:
            return "MultiPoint"
        elif number == QgsWkbTypes.MultiLineString:
            return "MultiLineString"
        elif number == QgsWkbTypes.MultiPolygon:
            return "MultiPolygon"
        elif number == QgsWkbTypes.NoGeometry:
            return "NoGeometry"
        elif number == QgsWkbTypes.Point25D:
            return "Point25D"
        elif number == QgsWkbTypes.LineString25D:
            return "LineString25D"
        elif number == QgsWkbTypes.Polygon25D:
            return "Polygon25D"
        elif number == QgsWkbTypes.MultiPoint25D:
            return "MultiPoint25D"
        elif number == QgsWkbTypes.MultiLineString25D:
            return "MultiLineString25D"
        elif number == QgsWkbTypes.MultiPolygon25D:
            return "MultiPolygon25D"
        else:
            self.showError('Unknown or invalid geometry type: ' + str(number))
            return "Don't know"
        # End of getwkbtext

    def killWorker(self):
        """Kill the worker thread."""
        # if self.worker is not None:
        #     self.showInfo(self.tr('Killing worker'))
        #     self.worker.kill()

    def showError(self, text):
        """Show an error."""
        self.iface.messageBar().pushMessage(self.tr('Error'), text,
                                            level=Qgis.Critical,
                                            duration=3)
        QgsMessageLog.logMessage('Error: ' + text, self.NNJOIN,
                                 Qgis.Critical)

    def showWarning(self, text):
        """Show a warning."""
        self.iface.messageBar().pushMessage(self.tr('Warning'), text,
                                            level=Qgis.Warning,
                                            duration=2)
        QgsMessageLog.logMessage('Warning: ' + text, self.NNJOIN,
                                 Qgis.Warning)

    def showInfo(self, text):
        """Show info."""
        self.iface.messageBar().pushMessage(self.tr('Info'), text,
                                            level=Qgis.Info,
                                            duration=2)
        QgsMessageLog.logMessage('Info: ' + text, self.NNJOIN,
                                 Qgis.Info)

    def help(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(
                         self.plugin_dir + "/help/html/index.html"))
        # showPluginHelp(None, "help/html/index")

    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        return QCoreApplication.translate('NNJoinDialog', message)
