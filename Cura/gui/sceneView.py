__copyright__ = "Copyright (C) 2013 David Braam - Released under terms of the AGPLv3 License"

import wx
import numpy
import time
import os
import json
import traceback
import threading
import math
import sys
import cStringIO as StringIO

import OpenGL
OpenGL.ERROR_CHECKING = False
from OpenGL.GLU import *
from OpenGL.GL import *

from Cura.util import profile
from Cura.util import meshLoader
from Cura.util import objectScene
from Cura.util import resources
from Cura.util import explorer
from Cura.gui.util import previewTools
from Cura.gui.util import openglHelpers
from Cura.gui.util import openglGui
from Cura.gui.tools import imageToMesh
from Cura.gui.tools import spectromUploadGui

class SelectObjectWindow(wx.Frame):
	def __init__(self, parent):
		super(SelectObjectWindow, self).__init__(parent, title="Select an object", style=wx.FRAME_TOOL_WINDOW|wx.FRAME_FLOAT_ON_PARENT|wx.FRAME_NO_TASKBAR)
		self._sceneView = parent
		self._panel = wx.Panel(self)
		self.SetSizer(wx.BoxSizer())
		self.GetSizer().Add(self._panel, 1, wx.EXPAND)

		title = wx.StaticText(self._panel, -1, _('Select an object to color'))
		title.SetFont(wx.Font(30, wx.SWISS, wx.NORMAL, wx.BOLD))

		cardImage = wx.StaticBitmap(self._panel, -1, wx.Bitmap(resources.getPathForImage('BusinessCardHolder.jpg')))
		cardButton = wx.Button(self._panel, -1, _("Color your work!"))
		cardText = wx.StaticText(self._panel, -1, _('Business Card Holder\nCreated by rhmorrison\nhttp://www.thingiverse.com/thing:28826'))
		self.Bind(wx.EVT_BUTTON, self.OnSelectCard, cardButton)
		cardButton.SetFont(wx.Font(20, wx.SWISS, wx.NORMAL, wx.NORMAL))
		cardText.SetFont(wx.Font(15, wx.SWISS, wx.NORMAL, wx.NORMAL))

		vaseImage = wx.StaticBitmap(self._panel, -1, wx.Bitmap(resources.getPathForImage('SpiralVase.jpg')))
		vaseButton = wx.Button(self._panel, -1, _("Color your life!"))
		vaseText = wx.StaticText(self._panel, -1, _('Spiral Vase\nCreated by anoved\nhttp://www.thingiverse.com/thing:275932'))
		self.Bind(wx.EVT_BUTTON, self.OnSelectVase, vaseButton)
		vaseButton.SetFont(wx.Font(20, wx.SWISS, wx.NORMAL, wx.NORMAL))
		vaseText.SetFont(wx.Font(15, wx.SWISS, wx.NORMAL, wx.NORMAL))

		dalekImage = wx.StaticBitmap(self._panel, -1, wx.Bitmap(resources.getPathForImage('DalekHoles.jpg')))
		dalekButton = wx.Button(self._panel, -1, _("EXTERMINATE!"))
		dalekText = wx.StaticText(self._panel, -1, _('Dalek\nCreated by RevK\nhttp://www.thingiverse.com/thing:192937'))
		self.Bind(wx.EVT_BUTTON, self.OnSelectDalek, dalekButton)
		dalekButton.SetFont(wx.Font(20, wx.SWISS, wx.NORMAL, wx.NORMAL))
		dalekText.SetFont(wx.Font(15, wx.SWISS, wx.NORMAL, wx.NORMAL))

		sizer = wx.GridBagSizer(4,3)
		sizer.Add(title, (0,0), span=(1,3), flag=wx.ALIGN_CENTRE | wx.ALL, border=5)

		sizer.Add(cardImage, (1,0), flag=wx.ALIGN_CENTRE | wx.ALL, border=5)
		sizer.Add(cardButton, (2,0), flag=wx.ALIGN_CENTRE | wx.EXPAND | wx.ALL, border=5)
		sizer.Add(cardText, (3,0), flag=wx.ALIGN_CENTRE | wx.ALL, border=5)

		sizer.Add(vaseImage, (1,1), flag=wx.ALIGN_CENTRE | wx.ALL, border=5)
		sizer.Add(vaseButton, (2,1), flag=wx.ALIGN_CENTRE | wx.EXPAND | wx.ALL, border=5)
		sizer.Add(vaseText, (3,1), flag=wx.ALIGN_CENTRE | wx.ALL, border=5)

		sizer.Add(dalekImage, (1,2), flag=wx.ALIGN_CENTRE | wx.ALL, border=5)
		sizer.Add(dalekButton, (2,2), flag=wx.ALIGN_CENTRE | wx.EXPAND | wx.ALL, border=5)
		sizer.Add(dalekText, (3,2), flag=wx.ALIGN_CENTRE | wx.ALL, border=5)

		self._panel.SetSizer(sizer)

		self.Fit()
		self.Centre()


	def OnSelectCard(self, button):
		self._sceneView.loadFiles([resources.getPathForMesh('BusinessCardHolder.stl'), resources.getPathForMesh('BusinessCardHolder.layers')])
		self.Hide()
		self.Destroy()

	def OnSelectVase(self, button):
		self._sceneView.loadFiles([resources.getPathForMesh('SpiralVase.stl'), resources.getPathForMesh('SpiralVase.layers')])
		self.Hide()
		self.Destroy()

	def OnSelectDalek(self, button):
		self._sceneView.loadFiles([resources.getPathForMesh('DalekHoles.stl'), resources.getPathForMesh('DalekHoles.layers')])
		self.Hide()
		self.Destroy()


class SceneView(openglGui.glGuiPanel):
	def __init__(self, parent):
		super(SceneView, self).__init__(parent)

		self._yaw = 30
		self._pitch = 60
		self._zoom = 300
		self._scene = objectScene.Scene()
		self._objectShader = None
		self._objectLoadShader = None
		self._focusObj = None
		self._selectedObj = None
		self._objColors = [None,None,None,None]
		self._mouseX = -1
		self._mouseY = -1
		self._mouseState = None
		self._viewTarget = numpy.array([0,0,0], numpy.float32)
		self._animView = None
		self._animZoom = None
		self._platformMesh = {}
		self._platformTexture = None

		self._viewport = None
		self._modelMatrix = None
		self._projMatrix = None
		self.tempMatrix = None

		self.openFileButton = openglGui.glButton(self, 4, _("Load Object"), (0.5,0.15), self.OnSelectObject)
		self.openFileButton.setForceText(True)
		self.spectromButton = openglGui.glButton(self, 20, _("Order This Object"), (-1.5,0.15), self.OnUploadButton)
		self.spectromButton.setDisabled(True)
		self.spectromButton.setForceText(True)
#		self.saveLayersButton = openglGui.glButton(self, 3, _("Save Colors"), (2,0), self.showSaveMetadata)
#		self.saveLayersButton.setDisabled(True)

#		group = []
#		self.rotateToolButton = openglGui.glRadioButton(self, 8, _("Rotate"), (0,-1), group, self.OnToolSelect)
#		self.scaleToolButton  = openglGui.glRadioButton(self, 9, _("Scale"), (1,-1), group, self.OnToolSelect)
#		self.mirrorToolButton  = openglGui.glRadioButton(self, 10, _("Mirror"), (2,-1), group, self.OnToolSelect)
#
#		self.resetRotationButton = openglGui.glButton(self, 12, _("Reset"), (0,-2), self.OnRotateReset)
#		self.layFlatButton       = openglGui.glButton(self, 16, _("Lay flat"), (0,-3), self.OnLayFlat)
#
#		self.resetScaleButton    = openglGui.glButton(self, 13, _("Reset"), (1,-2), self.OnScaleReset)
#		self.scaleMaxButton      = openglGui.glButton(self, 17, _("To max"), (1,-3), self.OnScaleMax)
#
#		self.mirrorXButton       = openglGui.glButton(self, 14, _("Mirror X"), (2,-2), lambda button: self.OnMirror(0))
#		self.mirrorYButton       = openglGui.glButton(self, 18, _("Mirror Y"), (2,-3), lambda button: self.OnMirror(1))
#		self.mirrorZButton       = openglGui.glButton(self, 22, _("Mirror Z"), (2,-4), lambda button: self.OnMirror(2))
#
#		self.rotateToolButton.setExpandArrow(True)
#		self.scaleToolButton.setExpandArrow(True)
#		self.mirrorToolButton.setExpandArrow(True)
#
#		self.scaleForm = openglGui.glFrame(self, (2, -2))
#		openglGui.glGuiLayoutGrid(self.scaleForm)
#		openglGui.glLabel(self.scaleForm, _("Scale X"), (0,0))
#		self.scaleXctrl = openglGui.glNumberCtrl(self.scaleForm, '1.0', (1,0), lambda value: self.OnScaleEntry(value, 0))
#		openglGui.glLabel(self.scaleForm, _("Scale Y"), (0,1))
#		self.scaleYctrl = openglGui.glNumberCtrl(self.scaleForm, '1.0', (1,1), lambda value: self.OnScaleEntry(value, 1))
#		openglGui.glLabel(self.scaleForm, _("Scale Z"), (0,2))
#		self.scaleZctrl = openglGui.glNumberCtrl(self.scaleForm, '1.0', (1,2), lambda value: self.OnScaleEntry(value, 2))
#		openglGui.glLabel(self.scaleForm, _("Size X (mm)"), (0,4))
#		self.scaleXmmctrl = openglGui.glNumberCtrl(self.scaleForm, '0.0', (1,4), lambda value: self.OnScaleEntryMM(value, 0))
#		openglGui.glLabel(self.scaleForm, _("Size Y (mm)"), (0,5))
#		self.scaleYmmctrl = openglGui.glNumberCtrl(self.scaleForm, '0.0', (1,5), lambda value: self.OnScaleEntryMM(value, 1))
#		openglGui.glLabel(self.scaleForm, _("Size Z (mm)"), (0,6))
#		self.scaleZmmctrl = openglGui.glNumberCtrl(self.scaleForm, '0.0', (1,6), lambda value: self.OnScaleEntryMM(value, 2))
#		openglGui.glLabel(self.scaleForm, _("Uniform scale"), (0,8))
#		self.scaleUniform = openglGui.glCheckbox(self.scaleForm, True, (1,8), None)

		self.layerColors = openglGui.glColorRangeSelect(self, (-0.5, -0.6), 0, 1950, (1,1,1), lambda: self.updateColor())
		self.layerColorer = openglGui.glColorPicker(self, (0, -3.7), (1,1,1), lambda: self.layerColors.setColor(self.layerColorer.getColor()))

		self.notification = openglGui.glNotification(self, (0, 0))

		self.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
		self.Bind(wx.EVT_LEAVE_WINDOW, self.OnMouseLeave)

		self.viewMode = 'layerColors'
		self.QueueRefresh()
		self.OnToolSelect(0)
		self.updateToolButtons()
		self.updateProfileToControls()
		self.updateColor()

	def OnSelectObject(self, button):
		self.OnDeleteAll(None)
		window = SelectObjectWindow(self)
		window.Show()

	def OnUploadButton(self, button):
		colors = StringIO.StringIO()
		self._saveMetadata(colors)
		spectromUploadGui.spectromUploadManager(self.GetTopLevelParent(), self._scene, colors.getvalue(), button != 1)
		colors.close()

	def updateColor(self):
		self._minSelectedLayer = self.layerColors.getMinSelect()
		self._maxSelectedLayer = self.layerColors.getMaxSelect()
		self._colorLayers = self.layerColors.getLayers()
		self._colorColors = self.layerColors.getColors()

	def saveMetadataFile(self, filename):
		f = open(filename, 'w')
		self._saveMetadata(f)
		f.close()

	def _saveMetadata(self, stream):
		obj = { \
			"colors": self._colorColors, \
			"layers": self._colorLayers \
		}
		json.dump(obj, stream)

	def loadMetadataFile(self, filename):
		f = open(filename, 'r')
		self._loadMetadata(f)
		f.close()

	def _loadMetadata(self, stream):
		if len(self._scene.objects()) == 0:
			self.notification.message("Please load a model before applying colors")
			return
		message = ''
		obj = "Couldn't parse JSON"
		try:
			obj = json.load(stream)
			if not 'colors' in obj:
				print "Load Error: No colors"
				raise ValueError
			if not 'layers' in obj:
				print "Load Error: No layers"
				raise ValueError
			colors = obj['colors']
			layers = obj['layers']
			# validate types
			if not isinstance(colors, list):
				print "Load Error: Colors is not a list"
				raise ValueError
			if not isinstance(layers, list):
				print "Load Error: Layers is not a list"
				raise ValueError
			# validate lengths
			if len(colors) != len(layers):
				print "Load Error: Layers and Colors are different sizes"
				raise ValueError
			if len(colors) < 1:
				print "Load Error: Layers and Colors lists are empty"
				raise ValueError
			# validate values
			for n in xrange(len(layers)-1):
				if layers[n] >= layers[n+1]:
					print "Load Error: layers[%d] is out of order" % (n+1)
					raise ValueError
			if layers[0] <= 0:
				print "Load Error: nonpositive layers"
				raise ValueError
			for n in xrange(len(colors)):
				if not isinstance(colors[n], list):
					print "Load Error: colors[%d] is not a list" % (n)
					raise ValueError
				if len(colors[n]) != 3:
					print "Load Error: colors[%d] has the wrong length" % (n)
					raise ValueError

			# Implant new colors
			# TODO: This is a hack
			self.layerColors.deselectAll()
			# get number of layers
			numLayers = layers[-1]
			trueLayers = self.layerColors._maxValue
			# set up rangeSelect as if it contained loaded data
			self.layerColors._maxValue = numLayers
			self.layerColors._colors = colors
			self.layerColors._layers = layers
			# scale data to fit loaded models
			if numLayers != trueLayers:
				print "Warning: Layer profile has different number of layers. Scaled."
				message = "Warning: Layer profile has different size. Scaled to fit."
				self.layerColors.setRange(0, trueLayers)

			self.updateColor()
		except ValueError:
			print "Offending data:"
			print obj
			message = "Couldn't load data. Check log for details."

		if message:
			self.notification.message(message)

	def loadSceneFiles(self, filenames):
		self.spectromButton.setDisabled(False)
#		self.saveLayersButton.setDisabled(False)
		self.loadScene(filenames)

	def loadFiles(self, filenames):
		mainWindow = self.GetParent().GetParent()
		# only one GCODE file can be active
		# so if single gcode file, process this
		# otherwise ignore all gcode files
		gcodeFilename = None
		spectromFilename = None
		if len(filenames) == 1:
			filename = filenames[0]
			ext = os.path.splitext(filename)[1].lower()
			if ext == '.g' or ext == '.gcode':
				gcodeFilename = filename
		if gcodeFilename is not None:
			self.notification.message("Spectrom does not yet support pre-sliced G-Code files.")
		else:
			# process directories and special file types
			# and keep scene files for later processing
			scene_filenames = []
			ignored_types = dict()
			# use file list as queue
			# pop first entry for processing and append new files at end
			while filenames:
				filename = filenames.pop(0)
				if os.path.isdir(filename):
					# directory: queue all included files and directories
					filenames.extend(os.path.join(filename, f) for f in os.listdir(filename))
				else:
					ext = os.path.splitext(filename)[1].lower()
					if ext in meshLoader.loadSupportedExtensions() or ext in imageToMesh.supportedExtensions():
						scene_filenames.append(filename)
						mainWindow.addToModelMRU(filename)
					elif ext == '.layers' or ext == '.layerspec':
						if spectromFilename is not None:
							ignored_types[filename] = 1
						else:
							spectromFilename = filename
					else:
						ignored_types[ext] = 1
			if ignored_types:
				ignored_types = ignored_types.keys()
				ignored_types.sort()
				self.notification.message("ignored: " + " ".join("*" + type for type in ignored_types))
			mainWindow.updateProfileToAllControls()
			# now process all the scene files
			if scene_filenames:
				self.loadSceneFiles(scene_filenames)
				self._selectObject(None)
				self.sceneUpdated()
				newZoom = numpy.max(self._machineSize)
				self._animView = openglGui.animation(self, self._viewTarget.copy(), numpy.array([0,0,0], numpy.float32), 0.5)
				self._animZoom = openglGui.animation(self, self._zoom, newZoom, 0.5)
			if spectromFilename is not None:
				self.loadMetadataFile(spectromFilename)

	def reloadScene(self, e):
		# Copy the list before DeleteAll clears it
		fileList = []
		for obj in self._scene.objects():
			fileList.append(obj.getOriginFilename())
		self.OnDeleteAll(None)
		self.loadScene(fileList)

	def showLoadFile(self, button = 1):
		if button == 1:
			dlg=wx.FileDialog(self, _("Open 3D model"), os.path.split(profile.getPreference('lastFile'))[0], style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST|wx.FD_MULTIPLE)

			wildcardList = ';'.join(map(lambda s: '*' + s, meshLoader.loadSupportedExtensions() + imageToMesh.supportedExtensions() + ['.layers', '.layerspec']))
			wildcardFilter = "All (%s)|%s;%s" % (wildcardList, wildcardList, wildcardList.upper())
			wildcardList = ';'.join(map(lambda s: '*' + s, meshLoader.loadSupportedExtensions()))
			wildcardFilter += "|Mesh files (%s)|%s;%s" % (wildcardList, wildcardList, wildcardList.upper())
			wildcardList = ';'.join(map(lambda s: '*' + s, imageToMesh.supportedExtensions()))
			wildcardFilter += "|Image files (%s)|%s;%s" % (wildcardList, wildcardList, wildcardList.upper())
			wildcardList = '*.layers;*.layerspec'
			wildcardFilter += "|Layer files (%s)|%s;%s" % (wildcardList, wildcardList, wildcardList.upper())

			dlg.SetWildcard(wildcardFilter)
			if dlg.ShowModal() != wx.ID_OK:
				dlg.Destroy()
				return
			filenames = dlg.GetPaths()
			dlg.Destroy()
			if len(filenames) < 1:
				return False
			profile.putPreference('lastFile', filenames[0])
			self.loadFiles(filenames)

	def showSaveModel(self, button = 1):
		if len(self._scene.objects()) < 1:
			return
		dlg=wx.FileDialog(self, _("Save 3D model"), os.path.split(profile.getPreference('lastFile'))[0], style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT)
		fileExtensions = meshLoader.saveSupportedExtensions()
		wildcardList = ';'.join(map(lambda s: '*' + s, fileExtensions))
		wildcardFilter = "Mesh files (%s)|%s;%s" % (wildcardList, wildcardList, wildcardList.upper())
		dlg.SetWildcard(wildcardFilter)
		if dlg.ShowModal() != wx.ID_OK:
			dlg.Destroy()
			return
		filename = dlg.GetPath()
		dlg.Destroy()
		meshLoader.saveMeshes(filename, self._scene.objects())

	def showSaveMetadata(self, button = 1):
		if len(self._scene.objects()) < 1:
			return
		dlg=wx.FileDialog(self, _("Save Layer Profile"), os.path.split(profile.getPreference('lastFile'))[0], style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT)
		fileExtensions = ['.layers']
		wildcardList = ';'.join(map(lambda s: '*' + s, fileExtensions))
		wildcardFilter = "Spectrom layer files (%s)|%s;%s" % (wildcardList, wildcardList, wildcardList.upper())
		dlg.SetWildcard(wildcardFilter)
		if dlg.ShowModal() != wx.ID_OK:
			dlg.Destroy()
			return
		filename = dlg.GetPath()
		dlg.Destroy()
		self.saveMetadataFile(filename)

	def OnToolSelect(self, button):
#		if self.rotateToolButton.getSelected():
#			self.tool = previewTools.toolRotate(self)
#		elif self.scaleToolButton.getSelected():
#			self.tool = previewTools.toolScale(self)
#		elif self.mirrorToolButton.getSelected():
#			self.tool = previewTools.toolNone(self)
#		else:
		self.tool = previewTools.toolNone(self)
#		self.resetRotationButton.setHidden(not self.rotateToolButton.getSelected())
#		self.layFlatButton.setHidden(not self.rotateToolButton.getSelected())
#		self.resetScaleButton.setHidden(not self.scaleToolButton.getSelected())
#		self.scaleMaxButton.setHidden(not self.scaleToolButton.getSelected())
#		self.scaleForm.setHidden(not self.scaleToolButton.getSelected())
#		self.mirrorXButton.setHidden(not self.mirrorToolButton.getSelected())
#		self.mirrorYButton.setHidden(not self.mirrorToolButton.getSelected())
#		self.mirrorZButton.setHidden(not self.mirrorToolButton.getSelected())

	def updateToolButtons(self):
		pass
#		if self._selectedObj is None:
#			hidden = True
#		else:
#			hidden = False
#		self.rotateToolButton.setHidden(hidden)
#		self.scaleToolButton.setHidden(hidden)
#		self.mirrorToolButton.setHidden(hidden)
#		if hidden:
#			self.rotateToolButton.setSelected(False)
#			self.scaleToolButton.setSelected(False)
#			self.mirrorToolButton.setSelected(False)
#			self.OnToolSelect(0)

	def OnRotateReset(self, button):
		if self._selectedObj is None:
			return
		self._selectedObj.resetRotation()
		self._scene.pushFree(self._selectedObj)
		self._selectObject(self._selectedObj)
		self.sceneUpdated()

	def OnLayFlat(self, button):
		if self._selectedObj is None:
			return
		self._selectedObj.layFlat()
		self._scene.pushFree(self._selectedObj)
		self._selectObject(self._selectedObj)
		self.sceneUpdated()

	def OnScaleReset(self, button):
		if self._selectedObj is None:
			return
		self._selectedObj.resetScale()
		self._selectObject(self._selectedObj)
		self.updateProfileToControls()
		self.sceneUpdated()

	def OnScaleMax(self, button):
		if self._selectedObj is None:
			return
		machine = profile.getMachineSetting('machine_type')
		self._selectedObj.setPosition(numpy.array([0.0, 0.0]))
		self._scene.pushFree(self._selectedObj)
		#self.sceneUpdated()
		if machine == "ultimaker2":
			#This is bad and Jaime should feel bad!
			self._selectedObj.setPosition(numpy.array([0.0,-10.0]))
			self._selectedObj.scaleUpTo(self._machineSize - numpy.array(profile.calculateObjectSizeOffsets() + [0.0], numpy.float32) * 2 - numpy.array([3,3,3], numpy.float32))
			self._selectedObj.setPosition(numpy.array([0.0,0.0]))
			self._scene.pushFree(self._selectedObj)
		else:
			self._selectedObj.setPosition(numpy.array([0.0, 0.0]))
			self._scene.pushFree(self._selectedObj)
			self._selectedObj.scaleUpTo(self._machineSize - numpy.array(profile.calculateObjectSizeOffsets() + [0.0], numpy.float32) * 2 - numpy.array([3,3,3], numpy.float32))
		self._scene.pushFree(self._selectedObj)
		self._selectObject(self._selectedObj)
		self.updateProfileToControls()
		self.sceneUpdated()

	def OnMirror(self, axis):
		if self._selectedObj is None:
			return
		self._selectedObj.mirror(axis)
		self.sceneUpdated()

	def OnScaleEntry(self, value, axis):
		if self._selectedObj is None:
			return
		try:
			value = float(value)
		except:
			return
		self._selectedObj.setScale(value, axis, self.scaleUniform.getValue())
		self.updateProfileToControls()
		self._scene.pushFree(self._selectedObj)
		self._selectObject(self._selectedObj)
		self.sceneUpdated()

	def OnScaleEntryMM(self, value, axis):
		if self._selectedObj is None:
			return
		try:
			value = float(value)
		except:
			return
		self._selectedObj.setSize(value, axis, self.scaleUniform.getValue())
		self.updateProfileToControls()
		self._scene.pushFree(self._selectedObj)
		self._selectObject(self._selectedObj)
		self.sceneUpdated()

	def OnDeleteAll(self, e):
		while len(self._scene.objects()) > 0:
			self._deleteObject(self._scene.objects()[0])
		self._animView = openglGui.animation(self, self._viewTarget.copy(), numpy.array([0,0,0], numpy.float32), 0.5)

	def OnMultiply(self, e):
		if self._focusObj is None:
			return
		obj = self._focusObj
		dlg = wx.NumberEntryDialog(self, _("How many copies do you want?"), _("Number of copies"), _("Multiply"), 1, 1, 100)
		if dlg.ShowModal() != wx.ID_OK:
			dlg.Destroy()
			return
		cnt = dlg.GetValue()
		dlg.Destroy()
		n = 0
		while True:
			n += 1
			newObj = obj.copy()
			self._scene.add(newObj)
			self._scene.centerAll()
			if not self._scene.checkPlatform(newObj):
				break
			if n > cnt:
				break
		if n <= cnt:
			self.notification.message("Could not create more than %d items" % (n - 1))
		self._scene.remove(newObj)
		self._scene.centerAll()
		self.sceneUpdated()

	def OnSplitObject(self, e):
		if self._focusObj is None:
			return
		self._scene.remove(self._focusObj)
		for obj in self._focusObj.split(self._splitCallback):
			if numpy.max(obj.getSize()) > 2.0:
				self._scene.add(obj)
		self._scene.centerAll()
		self._selectObject(None)
		self.sceneUpdated()

	def OnCenter(self, e):
		if self._focusObj is None:
			return
		self._focusObj.setPosition(numpy.array([0.0, 0.0]))
		self._scene.pushFree(self._selectedObj)
		newViewPos = numpy.array([self._focusObj.getPosition()[0], self._focusObj.getPosition()[1], self._focusObj.getSize()[2] / 2])
		self._animView = openglGui.animation(self, self._viewTarget.copy(), newViewPos, 0.5)
		self.sceneUpdated()

	def _splitCallback(self, progress):
		print progress

	def OnMergeObjects(self, e):
		if self._selectedObj is None or self._focusObj is None or self._selectedObj == self._focusObj:
			if len(self._scene.objects()) == 2:
				self._scene.merge(self._scene.objects()[0], self._scene.objects()[1])
				self.sceneUpdated()
			return
		self._scene.merge(self._selectedObj, self._focusObj)
		self.sceneUpdated()

	def sceneUpdated(self):
		self._scene.updateSizeOffsets()
		self.updateLayerRange()
		self.QueueRefresh()
		if len(self._scene.objects()) == 0:
			self.spectromButton.setDisabled(True)
#			self.saveLayersButton.setDisabled(True)


	def loadScene(self, fileList):
		for filename in fileList:
			try:
				ext = os.path.splitext(filename)[1].lower()
				if ext in imageToMesh.supportedExtensions():
					imageToMesh.convertImageDialog(self, filename).Show()
					objList = []
				else:
					objList = meshLoader.loadMeshes(filename)
			except:
				traceback.print_exc()
			else:
				for obj in objList:
					if self._objectLoadShader is not None:
						obj._loadAnim = openglGui.animation(self, 1, 0, 1.5)
					else:
						obj._loadAnim = None
					self._scene.add(obj)
					if not self._scene.checkPlatform(obj):
						self._scene.centerAll()
					self._selectObject(obj)
					if obj.getScale()[0] < 1.0:
						self.notification.message("Warning: Object scaled down.")
		self.sceneUpdated()

	def _deleteObject(self, obj):
		if obj == self._selectedObj:
			self._selectObject(None)
		if obj == self._focusObj:
			self._focusObj = None
		self._scene.remove(obj)
		for m in obj._meshList:
			if m.vbo is not None and m.vbo.decRef():
				self.glReleaseList.append(m.vbo)
		import gc
		gc.collect()
		self.sceneUpdated()

	def _selectObject(self, obj, zoom = True):
		if obj != self._selectedObj:
			self._selectedObj = obj
			self.updateModelSettingsToControls()
			self.updateToolButtons()
		if zoom and obj is not None:
			newViewPos = numpy.array([obj.getPosition()[0], obj.getPosition()[1], obj.getSize()[2] / 2])
			self._animView = openglGui.animation(self, self._viewTarget.copy(), newViewPos, 0.5)
			newZoom = obj.getBoundaryCircle() * 6
			if newZoom > numpy.max(self._machineSize) * 3:
				newZoom = numpy.max(self._machineSize) * 3
			self._animZoom = openglGui.animation(self, self._zoom, newZoom, 0.5)

	def updateProfileToControls(self):
		self._scene.updateSizeOffsets(True)
		self._machineSize = numpy.array([profile.getMachineSettingFloat('machine_width'), profile.getMachineSettingFloat('machine_depth'), profile.getMachineSettingFloat('machine_height')])
		self._objColors[0] = profile.getPreferenceColour('model_colour')
		self._objColors[1] = profile.getPreferenceColour('model_colour2')
		self._objColors[2] = profile.getPreferenceColour('model_colour3')
		self._objColors[3] = profile.getPreferenceColour('model_colour4')
		self._scene.updateMachineDimensions()
		self.updateModelSettingsToControls()
		self.updateLayerRange()


	def updateModelSettingsToControls(self):
		pass
#		if self._selectedObj is not None:
#			scale = self._selectedObj.getScale()
#			size = self._selectedObj.getSize()
#			self.scaleXctrl.setValue(round(scale[0], 2))
#			self.scaleYctrl.setValue(round(scale[1], 2))
#			self.scaleZctrl.setValue(round(scale[2], 2))
#			self.scaleXmmctrl.setValue(round(size[0], 2))
#			self.scaleYmmctrl.setValue(round(size[1], 2))
#			self.scaleZmmctrl.setValue(round(size[2], 2))

	def updateLayerRange(self):
		self._layerHeight = profile.getProfileSettingFloat('layer_height')
		objects = self._scene.objects()
		if len(objects) > 0:
			tallestObject = max(objects, key=lambda obj : obj.getSize()[2])
			numLayers = int(math.ceil(tallestObject.getSize()[2] / self._layerHeight))
			self.layerColors.setRange(0, max(numLayers, 1))
		else:
			self.layerColors.setRange(0, 1)

	def OnKeyChar(self, keyCode):
		if keyCode == wx.WXK_DELETE or keyCode == wx.WXK_NUMPAD_DELETE or (keyCode == wx.WXK_BACK and sys.platform.startswith("darwin")):
			if self._selectedObj is not None:
				self._deleteObject(self._selectedObj)
				self.QueueRefresh()
		if keyCode == wx.WXK_UP:
			if wx.GetKeyState(wx.WXK_SHIFT):
				self._zoom /= 1.2
				if self._zoom < 1:
					self._zoom = 1
			else:
				self._pitch -= 15
			self.QueueRefresh()
		elif keyCode == wx.WXK_DOWN:
			if wx.GetKeyState(wx.WXK_SHIFT):
				self._zoom *= 1.2
				if self._zoom > numpy.max(self._machineSize) * 3:
					self._zoom = numpy.max(self._machineSize) * 3
			else:
				self._pitch += 15
			self.QueueRefresh()
		elif keyCode == wx.WXK_LEFT:
			self._yaw -= 15
			self.QueueRefresh()
		elif keyCode == wx.WXK_RIGHT:
			self._yaw += 15
			self.QueueRefresh()
		elif keyCode == wx.WXK_NUMPAD_ADD or keyCode == wx.WXK_ADD or keyCode == ord('+') or keyCode == ord('='):
			self._zoom /= 1.2
			if self._zoom < 1:
				self._zoom = 1
			self.QueueRefresh()
		elif keyCode == wx.WXK_NUMPAD_SUBTRACT or keyCode == wx.WXK_SUBTRACT or keyCode == ord('-'):
			self._zoom *= 1.2
			if self._zoom > numpy.max(self._machineSize) * 3:
				self._zoom = numpy.max(self._machineSize) * 3
			self.QueueRefresh()
		elif keyCode == wx.WXK_HOME:
			self._yaw = 30
			self._pitch = 60
			self.QueueRefresh()
		elif keyCode == wx.WXK_PAGEUP:
			self._yaw = 0
			self._pitch = 0
			self.QueueRefresh()
		elif keyCode == wx.WXK_PAGEDOWN:
			self._yaw = 0
			self._pitch = 90
			self.QueueRefresh()
		elif keyCode == wx.WXK_END:
			self._yaw = 90
			self._pitch = 90
			self.QueueRefresh()

		if keyCode == wx.WXK_F3 and wx.GetKeyState(wx.WXK_SHIFT):
			shaderEditor(self, self.ShaderUpdate, self._objectLoadShader.getVertexShader(), self._objectLoadShader.getFragmentShader())
		if keyCode == wx.WXK_F4 and wx.GetKeyState(wx.WXK_SHIFT):
			from collections import defaultdict
			from gc import get_objects
			self._beforeLeakTest = defaultdict(int)
			for i in get_objects():
				self._beforeLeakTest[type(i)] += 1
		if keyCode == wx.WXK_F5 and wx.GetKeyState(wx.WXK_SHIFT):
			from collections import defaultdict
			from gc import get_objects
			self._afterLeakTest = defaultdict(int)
			for i in get_objects():
				self._afterLeakTest[type(i)] += 1
			for k in self._afterLeakTest:
				if self._afterLeakTest[k]-self._beforeLeakTest[k]:
					print k, self._afterLeakTest[k], self._beforeLeakTest[k], self._afterLeakTest[k] - self._beforeLeakTest[k]

	def ShaderUpdate(self, v, f):
		s = openglHelpers.GLShader(v, f)
		if s.isValid():
			self._objectLoadShader.release()
			self._objectLoadShader = s
			for obj in self._scene.objects():
				obj._loadAnim = openglGui.animation(self, 1, 0, 1.5)
			self.QueueRefresh()

	def OnMouseDown(self,e):
		self._mouseX = e.GetX()
		self._mouseY = e.GetY()
		self._mouseClick3DPos = self._mouse3Dpos
		self._mouseClickFocus = self._focusObj
		if e.ButtonDClick():
			self._mouseState = 'doubleClick'
		else:
			if self._mouseState == 'dragObject' and self._selectedObj is not None:
				self._scene.pushFree(self._selectedObj)
				self.sceneUpdated()
			self._mouseState = 'dragOrClick'
		p0, p1 = self.getMouseRay(self._mouseX, self._mouseY)
		p0 -= self.getObjectCenterPos() - self._viewTarget
		p1 -= self.getObjectCenterPos() - self._viewTarget
		if self.tool.OnDragStart(p0, p1):
			self._mouseState = 'tool'
		if self._mouseState == 'dragOrClick':
			if e.GetButton() == 1:
				if self._focusObj is not None:
					self._selectObject(self._focusObj, False)
					self.QueueRefresh()

	def OnMouseUp(self, e):
		if e.LeftIsDown() or e.MiddleIsDown() or e.RightIsDown():
			return
		if self._mouseState == 'dragOrClick':
			if e.GetButton() == 1:
				self._selectObject(self._focusObj)
			if e.GetButton() == 3:
					menu = wx.Menu()
					if self._focusObj is not None:

						self.Bind(wx.EVT_MENU, self.OnCenter, menu.Append(-1, _("Center on platform")))
						self.Bind(wx.EVT_MENU, lambda e: self._deleteObject(self._focusObj), menu.Append(-1, _("Delete object")))
						self.Bind(wx.EVT_MENU, self.OnMultiply, menu.Append(-1, _("Multiply object")))
						self.Bind(wx.EVT_MENU, self.OnSplitObject, menu.Append(-1, _("Split object into parts")))
					if ((self._selectedObj != self._focusObj and self._focusObj is not None and self._selectedObj is not None) or len(self._scene.objects()) == 2) and int(profile.getMachineSetting('extruder_amount')) > 1:
						self.Bind(wx.EVT_MENU, self.OnMergeObjects, menu.Append(-1, _("Dual extrusion merge")))
					if len(self._scene.objects()) > 0:
						self.Bind(wx.EVT_MENU, self.OnDeleteAll, menu.Append(-1, _("Delete all objects")))
						self.Bind(wx.EVT_MENU, self.reloadScene, menu.Append(-1, _("Reload all objects")))
					if menu.MenuItemCount > 0:
						self.PopupMenu(menu)
					menu.Destroy()
		elif self._mouseState == 'dragObject' and self._selectedObj is not None:
			self._scene.pushFree(self._selectedObj)
			self.sceneUpdated()
		elif self._mouseState == 'tool':
			if self.tempMatrix is not None and self._selectedObj is not None:
				self._selectedObj.applyMatrix(self.tempMatrix)
				self._scene.pushFree(self._selectedObj)
				self._selectObject(self._selectedObj)
			self.tempMatrix = None
			self.tool.OnDragEnd()
			self.sceneUpdated()
		self._mouseState = None

	def OnMouseMotion(self,e):
		p0, p1 = self.getMouseRay(e.GetX(), e.GetY())
		p0 -= self.getObjectCenterPos() - self._viewTarget
		p1 -= self.getObjectCenterPos() - self._viewTarget

		if e.Dragging() and self._mouseState is not None:
			if self._mouseState == 'tool':
				self.tool.OnDrag(p0, p1)
			elif not e.LeftIsDown() and e.RightIsDown() or e.LeftIsDown() and not e.RightIsDown() and self._mouseClickFocus is None:
				self._mouseState = 'drag'
				if wx.GetKeyState(wx.WXK_SHIFT):
					a = math.cos(math.radians(self._yaw)) / 3.0
					b = math.sin(math.radians(self._yaw)) / 3.0
					self._viewTarget[0] += float(e.GetX() - self._mouseX) * -a
					self._viewTarget[1] += float(e.GetX() - self._mouseX) * b
					self._viewTarget[0] += float(e.GetY() - self._mouseY) * b
					self._viewTarget[1] += float(e.GetY() - self._mouseY) * a
				else:
					self._yaw += e.GetX() - self._mouseX
					self._pitch -= e.GetY() - self._mouseY
				if self._pitch > 170:
					self._pitch = 170
				if self._pitch < 10:
					self._pitch = 10
			elif (e.LeftIsDown() and e.RightIsDown()) or e.MiddleIsDown():
				self._mouseState = 'drag'
				self._zoom += e.GetY() - self._mouseY
				if self._zoom < 1:
					self._zoom = 1
				if self._zoom > numpy.max(self._machineSize) * 3:
					self._zoom = numpy.max(self._machineSize) * 3
			elif e.LeftIsDown() and self._selectedObj is not None and self._selectedObj == self._mouseClickFocus:
				self._mouseState = 'dragObject'
				z = max(0, self._mouseClick3DPos[2])
				p0, p1 = self.getMouseRay(self._mouseX, self._mouseY)
				p2, p3 = self.getMouseRay(e.GetX(), e.GetY())
				p0[2] -= z
				p1[2] -= z
				p2[2] -= z
				p3[2] -= z
				cursorZ0 = p0 - (p1 - p0) * (p0[2] / (p1[2] - p0[2]))
				cursorZ1 = p2 - (p3 - p2) * (p2[2] / (p3[2] - p2[2]))
				diff = cursorZ1 - cursorZ0
				self._selectedObj.setPosition(self._selectedObj.getPosition() + diff[0:2])
		if not e.Dragging() or self._mouseState != 'tool':
			self.tool.OnMouseMove(p0, p1)

		self._mouseX = e.GetX()
		self._mouseY = e.GetY()

	def OnMouseWheel(self, e):
		delta = float(e.GetWheelRotation()) / float(e.GetWheelDelta())
		delta = max(min(delta,4),-4)
		self._zoom *= 1.0 - delta / 10.0
		if self._zoom < 1.0:
			self._zoom = 1.0
		if self._zoom > numpy.max(self._machineSize) * 3:
			self._zoom = numpy.max(self._machineSize) * 3
		self.Refresh()

	def OnMouseLeave(self, e):
		#self._mouseX = -1
		pass

	def getMouseRay(self, x, y):
		if self._viewport is None:
			return numpy.array([0,0,0],numpy.float32), numpy.array([0,0,1],numpy.float32)
		p0 = openglHelpers.unproject(x, self._viewport[1] + self._viewport[3] - y, 0, self._modelMatrix, self._projMatrix, self._viewport)
		p1 = openglHelpers.unproject(x, self._viewport[1] + self._viewport[3] - y, 1, self._modelMatrix, self._projMatrix, self._viewport)
		p0 -= self._viewTarget
		p1 -= self._viewTarget
		return p0, p1

	def _init3DView(self):
		# set viewing projection
		size = self.GetSize()
		glViewport(0, 0, size.GetWidth(), size.GetHeight())
		glLoadIdentity()

		glLightfv(GL_LIGHT0, GL_POSITION, [0.2, 0.2, 1.0, 0.0])

		glDisable(GL_RESCALE_NORMAL)
		glDisable(GL_LIGHTING)
		glDisable(GL_LIGHT0)
		glEnable(GL_DEPTH_TEST)
		glDisable(GL_CULL_FACE)
		glDisable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

		glClearColor(0.8, 0.8, 0.8, 1.0)
		glClearStencil(0)
		glClearDepth(1.0)

		glMatrixMode(GL_PROJECTION)
		glLoadIdentity()
		aspect = float(size.GetWidth()) / float(size.GetHeight())
		gluPerspective(45.0, aspect, 1.0, numpy.max(self._machineSize) * 4)

		glMatrixMode(GL_MODELVIEW)
		glLoadIdentity()
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT | GL_STENCIL_BUFFER_BIT)

	def OnPaint(self,e):
		if self._animView is not None:
			self._viewTarget = self._animView.getPosition()
			if self._animView.isDone():
				self._animView = None
		if self._animZoom is not None:
			self._zoom = self._animZoom.getPosition()
			if self._animZoom.isDone():
				self._animZoom = None
		if self._objectShader is None: #TODO: add loading shaders from file(s)
			if openglHelpers.hasShaderSupport():
				self._layerShader = openglHelpers.GLShader("""
					uniform mat4 model_matrix;

					varying float light_amount;
					varying vec3 vertex_position;

					void main(void)
					{
						gl_Position = gl_ModelViewProjectionMatrix * gl_Vertex;
						gl_FrontColor = gl_Color;

						vertex_position = vec3(model_matrix * gl_Vertex);
						//gl_Position = gl_ProjectionMatrix * (model_matrix * gl_Vertex);

						light_amount = abs(dot(normalize(gl_NormalMatrix * gl_Normal), normalize(gl_LightSource[0].position.xyz)));
						light_amount += 0.2;
					}
				""","""
					uniform int min_selected;
					uniform int max_selected;
					uniform int num_layers;
					uniform int layer_starts[64];
					uniform vec4 layer_colors[64];
					uniform float layer_height;

					varying float light_amount;
					varying vec3 vertex_position;

					vec4 getDistanceColor(void)
					{
						return vec4(vec3(1.0 - smoothstep(0, 100, length(vertex_position))), 1);
					}

					int getLayerIndex(int layer)
					{
						// binary search for closest preceding layer start, and return the associated color
						int lowerbound = 0;
						int upperbound = num_layers;
						int position = (lowerbound + upperbound) / 2;
						while(lowerbound < upperbound)
						{
							if (layer_starts[position] == layer)
								return position;
							else if (layer_starts[position] > layer)
								upperbound = position;
							else
								lowerbound = position + 1;
							position = (lowerbound + upperbound) / 2;
						}
						return position;
					}

					vec4 getLayerColor(int layer)
					{
						if (layer < 0)
							return getDistanceColor();
						int position = getLayerIndex(layer + 1); // Layer colors are (min, max]
						if (position >= num_layers)
							return layer_colors[num_layers - 1];
						return layer_colors[position];
					}

					void main(void)
					{
						int layer = int(vertex_position.z / layer_height);
						float selectDim = (layer >= min_selected && layer < max_selected) ? 0.5 : 1.0;
						vec4 color = getLayerColor(layer);
						gl_FragColor = vec4(color.rgb * (selectDim * light_amount), color.a);
					}
				""")
				self._objectShader = openglHelpers.GLShader("""
					varying float light_amount;

					void main(void)
					{
						gl_Position = gl_ModelViewProjectionMatrix * gl_Vertex;
						gl_FrontColor = gl_Color;

						light_amount = abs(dot(normalize(gl_NormalMatrix * gl_Normal), normalize(gl_LightSource[0].position.xyz)));
						light_amount += 0.2;
					}
				""","""
					varying float light_amount;

					void main(void)
					{
						gl_FragColor = vec4(gl_Color.xyz * light_amount, gl_Color[3]);
					}
				""")
				self._objectOverhangShader = openglHelpers.GLShader("""
					uniform float cosAngle;
					uniform mat3 rotMatrix;
					varying float light_amount;

					void main(void)
					{
						gl_Position = gl_ModelViewProjectionMatrix * gl_Vertex;
						gl_FrontColor = gl_Color;

						light_amount = abs(dot(normalize(gl_NormalMatrix * gl_Normal), normalize(gl_LightSource[0].position.xyz)));
						light_amount += 0.2;
						if (normalize(rotMatrix * gl_Normal).z < -cosAngle)
						{
							light_amount = -10.0;
						}
					}
				""","""
					varying float light_amount;

					void main(void)
					{
						if (light_amount == -10.0)
						{
							gl_FragColor = vec4(1.0, 0.0, 0.0, gl_Color[3]);
						}else{
							gl_FragColor = vec4(gl_Color.xyz * light_amount, gl_Color[3]);
						}
					}
									""")
				self._objectLoadShader = openglHelpers.GLShader("""
					uniform float intensity;
					uniform float scale;
					varying float light_amount;

					void main(void)
					{
						vec4 tmp = gl_Vertex;
						tmp.x += sin(tmp.z/5.0+intensity*30.0) * scale * intensity;
						tmp.y += sin(tmp.z/3.0+intensity*40.0) * scale * intensity;
						gl_Position = gl_ModelViewProjectionMatrix * tmp;
						gl_FrontColor = gl_Color;

						light_amount = abs(dot(normalize(gl_NormalMatrix * gl_Normal), normalize(gl_LightSource[0].position.xyz)));
						light_amount += 0.2;
					}
				""","""
					uniform float intensity;
					varying float light_amount;

					void main(void)
					{
						gl_FragColor = vec4(gl_Color.xyz * light_amount, 1.0-intensity);
					}
				""")
			if self._objectShader is None or not self._objectShader.isValid(): #Could not make shader.
				self._objectShader = openglHelpers.GLFakeShader()
				self._objectOverhangShader = openglHelpers.GLFakeShader()
				self._layerShader = openglHelpers.GLFakeShader()
				self._objectLoadShader = None
		self._init3DView()
		glTranslate(0,0,-self._zoom)
		glRotate(-self._pitch, 1,0,0)
		glRotate(self._yaw, 0,0,1)
		glTranslate(-self._viewTarget[0],-self._viewTarget[1],-self._viewTarget[2])

		self._viewport = glGetIntegerv(GL_VIEWPORT)
		self._modelMatrix = glGetDoublev(GL_MODELVIEW_MATRIX)
		self._projMatrix = glGetDoublev(GL_PROJECTION_MATRIX)

		glClearColor(1,1,1,1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT | GL_STENCIL_BUFFER_BIT)

		if self.viewMode != 'gcode':
			for n in xrange(0, len(self._scene.objects())):
				obj = self._scene.objects()[n]
				glColor4ub((n >> 16) & 0xFF, (n >> 8) & 0xFF, (n >> 0) & 0xFF, 0xFF)
				self._renderObject(obj)

		if self._mouseX > -1: # mouse has not passed over the opengl window.
			glFlush()
			n = glReadPixels(self._mouseX, self.GetSize().GetHeight() - 1 - self._mouseY, 1, 1, GL_RGBA, GL_UNSIGNED_INT_8_8_8_8)[0][0] >> 8
			if n < len(self._scene.objects()):
				self._focusObj = self._scene.objects()[n]
			else:
				self._focusObj = None
			f = glReadPixels(self._mouseX, self.GetSize().GetHeight() - 1 - self._mouseY, 1, 1, GL_DEPTH_COMPONENT, GL_FLOAT)[0][0]
			#self.GetTopLevelParent().SetTitle(hex(n) + " " + str(f))
			self._mouse3Dpos = openglHelpers.unproject(self._mouseX, self._viewport[1] + self._viewport[3] - self._mouseY, f, self._modelMatrix, self._projMatrix, self._viewport)
			self._mouse3Dpos -= self._viewTarget

		self._init3DView()
		glTranslate(0,0,-self._zoom)
		glRotate(-self._pitch, 1,0,0)
		glRotate(self._yaw, 0,0,1)
		glTranslate(-self._viewTarget[0],-self._viewTarget[1],-self._viewTarget[2])

		self._objectShader.unbind()
		if self.viewMode != 'gcode':
			glStencilFunc(GL_ALWAYS, 1, 1)
			glStencilOp(GL_INCR, GL_INCR, GL_INCR)

			if self.viewMode == 'overhang':
				self._objectOverhangShader.bind()
				self._objectOverhangShader.setUniform('cosAngle', math.cos(math.radians(90 - profile.getProfileSettingFloat('support_angle'))))
			elif self.viewMode == 'layerColors':
				self._layerShader.bind()
				self._layerShader.setUniform('num_layers', len(self._colorLayers))
				self._layerShader.setUniform('min_selected', self._minSelectedLayer)
				self._layerShader.setUniform('max_selected', self._maxSelectedLayer)
				self._layerShader.setUniformIntArray('layer_starts', self._colorLayers)
				self._layerShader.setUniformVec4Array('layer_colors', list((color[0], color[1], color[2], 1) for color in self._colorColors))
				self._layerShader.setUniform('layer_height', self._layerHeight)
			else:
				self._objectShader.bind()
			for obj in self._scene.objects():
				if obj._loadAnim is not None:
					if obj._loadAnim.isDone():
						obj._loadAnim = None
					else:
						continue
				brightness = 1.0
				if self._focusObj == obj:
					brightness = 1.2
				elif self._focusObj is not None or self._selectedObj is not None and obj != self._selectedObj:
					brightness = 0.8

				if self._selectedObj == obj or self._selectedObj is None:
					#If we want transparent, then first render a solid black model to remove the printer size lines.
					if self.viewMode == 'transparent':
						glColor4f(0, 0, 0, 0)
						self._renderObject(obj)
						glEnable(GL_BLEND)
						glBlendFunc(GL_ONE, GL_ONE)
						glDisable(GL_DEPTH_TEST)
						brightness *= 0.5
					if self.viewMode == 'xray':
						glColorMask(GL_FALSE, GL_FALSE, GL_FALSE, GL_FALSE)
					glStencilOp(GL_INCR, GL_INCR, GL_INCR)
					glEnable(GL_STENCIL_TEST)

				if self.viewMode == 'overhang':
					if self._selectedObj == obj and self.tempMatrix is not None:
						self._objectOverhangShader.setUniform('rotMatrix', obj.getMatrix() * self.tempMatrix)
					else:
						self._objectOverhangShader.setUniform('rotMatrix', obj.getMatrix())
				elif self.viewMode == 'layerColors':
					pos = obj.getPosition()
					height = -profile.getProfileSettingFloat('object_sink')
					offset = obj.getDrawOffset()
					modelMatrix = openglHelpers.convert3x3MatrixTo4x4(obj.getMatrix(), [-offset[0]+pos[0], -offset[1]+pos[1], -offset[2]+height])
					self._layerShader.setUniformMat4('model_matrix', modelMatrix)

				if not self._scene.checkPlatform(obj):
					glColor4f(0.5 * brightness, 0.5 * brightness, 0.5 * brightness, 0.8 * brightness)
					self._renderObject(obj)
				else:
					self._renderObject(obj, brightness)
				glDisable(GL_STENCIL_TEST)
				glDisable(GL_BLEND)
				glEnable(GL_DEPTH_TEST)
				glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE)

			if self.viewMode == 'xray':
				glPushMatrix()
				glLoadIdentity()
				glEnable(GL_STENCIL_TEST)
				glStencilOp(GL_KEEP, GL_KEEP, GL_KEEP) #Keep values
				glDisable(GL_DEPTH_TEST)
				for i in xrange(2, 15, 2): #All even values
					glStencilFunc(GL_EQUAL, i, 0xFF)
					glColor(float(i)/10, float(i)/10, float(i)/5)
					glBegin(GL_QUADS)
					glVertex3f(-1000,-1000,-10)
					glVertex3f( 1000,-1000,-10)
					glVertex3f( 1000, 1000,-10)
					glVertex3f(-1000, 1000,-10)
					glEnd()
				for i in xrange(1, 15, 2): #All odd values
					glStencilFunc(GL_EQUAL, i, 0xFF)
					glColor(float(i)/10, 0, 0)
					glBegin(GL_QUADS)
					glVertex3f(-1000,-1000,-10)
					glVertex3f( 1000,-1000,-10)
					glVertex3f( 1000, 1000,-10)
					glVertex3f(-1000, 1000,-10)
					glEnd()
				glPopMatrix()
				glDisable(GL_STENCIL_TEST)
				glEnable(GL_DEPTH_TEST)

			self._objectShader.unbind()

			glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
			glEnable(GL_BLEND)
			if self._objectLoadShader is not None:
				self._objectLoadShader.bind()
				glColor4f(0.2, 0.6, 1.0, 1.0)
				for obj in self._scene.objects():
					if obj._loadAnim is None:
						continue
					self._objectLoadShader.setUniform('intensity', obj._loadAnim.getPosition())
					self._objectLoadShader.setUniform('scale', obj.getBoundaryCircle() / 10)
					self._renderObject(obj)
				self._objectLoadShader.unbind()
				glDisable(GL_BLEND)

		self._drawMachine()

		if self.viewMode != 'gcode':
			#Draw the object box-shadow, so you can see where it will collide with other objects.
			if self._selectedObj is not None:
				glEnable(GL_BLEND)
				glEnable(GL_CULL_FACE)
				glColor4f(0,0,0,0.16)
				glDepthMask(False)
				for obj in self._scene.objects():
					glPushMatrix()
					glTranslatef(obj.getPosition()[0], obj.getPosition()[1], 0)
					glBegin(GL_TRIANGLE_FAN)
					for p in obj._boundaryHull[::-1]:
						glVertex3f(p[0], p[1], 0)
					glEnd()
					glPopMatrix()
				if self._scene.isOneAtATime(): #Check print sequence mode.
					glPushMatrix()
					glColor4f(0,0,0,0.06)
					glTranslatef(self._selectedObj.getPosition()[0], self._selectedObj.getPosition()[1], 0)
					glBegin(GL_TRIANGLE_FAN)
					for p in self._selectedObj._printAreaHull[::-1]:
						glVertex3f(p[0], p[1], 0)
					glEnd()
					glBegin(GL_TRIANGLE_FAN)
					for p in self._selectedObj._headAreaMinHull[::-1]:
						glVertex3f(p[0], p[1], 0)
					glEnd()
					glPopMatrix()
				glDepthMask(True)
				glDisable(GL_CULL_FACE)

			#Draw the outline of the selected object on top of everything else except the GUI.
			if self._selectedObj is not None and self._selectedObj._loadAnim is None:
				glDisable(GL_DEPTH_TEST)
				glEnable(GL_CULL_FACE)
				glEnable(GL_STENCIL_TEST)
				glDisable(GL_BLEND)
				glStencilFunc(GL_EQUAL, 0, 255)

				glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
				glLineWidth(2)
				glColor4f(1,1,1,0.5)
				self._renderObject(self._selectedObj)
				glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)

				glViewport(0, 0, self.GetSize().GetWidth(), self.GetSize().GetHeight())
				glDisable(GL_STENCIL_TEST)
				glDisable(GL_CULL_FACE)
				glEnable(GL_DEPTH_TEST)

			if self._selectedObj is not None:
				glPushMatrix()
				pos = self.getObjectCenterPos()
				glTranslate(pos[0], pos[1], pos[2])
				self.tool.OnDraw()
				glPopMatrix()
		if self.viewMode == 'overhang' and not openglHelpers.hasShaderSupport():
			glDisable(GL_DEPTH_TEST)
			glPushMatrix()
			glLoadIdentity()
			glTranslate(0,-4,-10)
			glColor4ub(60,60,60,255)
			openglHelpers.glDrawStringCenter(_("Overhang view not working due to lack of OpenGL shaders support."))
			glPopMatrix()
		elif self.viewMode == 'layerColors' and not openglHelpers.hasShaderSupport():
			glDisable(GL_DEPTH_TEST)
			glPushMatrix()
			glLoadIdentity()
			glTranslate(0,-4,-10)
			glColor4ub(60,60,60,255)
			openglHelpers.glDrawStringCenter(_("Colors view not working due to lack of OpenGL shaders support."))
			glPopMatrix()

	def _renderObject(self, obj, brightness = 0, addSink = True):
		glPushMatrix()
		if addSink:
			glTranslate(obj.getPosition()[0], obj.getPosition()[1], obj.getSize()[2] / 2 - profile.getProfileSettingFloat('object_sink'))
		else:
			glTranslate(obj.getPosition()[0], obj.getPosition()[1], obj.getSize()[2] / 2)

		if self.tempMatrix is not None and obj == self._selectedObj:
			glMultMatrixf(openglHelpers.convert3x3MatrixTo4x4(self.tempMatrix))

		offset = obj.getDrawOffset()
		glTranslate(-offset[0], -offset[1], -offset[2] - obj.getSize()[2] / 2)

		glMultMatrixf(openglHelpers.convert3x3MatrixTo4x4(obj.getMatrix()))

		n = 0
		for m in obj._meshList:
			if m.vbo is None:
				m.vbo = openglHelpers.GLVBO(GL_TRIANGLES, m.vertexes, m.normal)
			if brightness != 0:
				glColor4fv(map(lambda idx: idx * brightness, self._objColors[n]))
				n += 1
			m.vbo.render()
		glPopMatrix()

	def _drawMachine(self):
		glEnable(GL_CULL_FACE)
		glEnable(GL_BLEND)

		size = [profile.getMachineSettingFloat('machine_width'), profile.getMachineSettingFloat('machine_depth'), profile.getMachineSettingFloat('machine_height')]

		machine = profile.getMachineSetting('machine_type')
		if machine.startswith('ultimaker'):
			if machine not in self._platformMesh:
				meshes = meshLoader.loadMeshes(resources.getPathForMesh(machine + '_platform.stl'))
				if len(meshes) > 0:
					self._platformMesh[machine] = meshes[0]
				else:
					self._platformMesh[machine] = None
				if machine == 'ultimaker2' or machine == 'ultimaker_plus':
					self._platformMesh[machine]._drawOffset = numpy.array([0,-37,145], numpy.float32)
				else:
					self._platformMesh[machine]._drawOffset = numpy.array([0,0,2.5], numpy.float32)
			glColor4f(1,1,1,0.5)
			self._objectShader.bind()
			self._renderObject(self._platformMesh[machine], False, False)
			self._objectShader.unbind()

			#For the Ultimaker 2 render the texture on the back plate to show the Ultimaker2 text.
			if machine == 'ultimaker2' or machine == 'ultimaker_plus':
				if not hasattr(self._platformMesh[machine], 'texture'):
					if machine == 'ultimaker2':
						self._platformMesh[machine].texture = openglHelpers.loadGLTexture('Ultimaker2backplate.png')
					else:
						self._platformMesh[machine].texture = openglHelpers.loadGLTexture('UltimakerPlusbackplate.png')
				glBindTexture(GL_TEXTURE_2D, self._platformMesh[machine].texture)
				glEnable(GL_TEXTURE_2D)
				glPushMatrix()
				glColor4f(1,1,1,1)

				glTranslate(0,150,-5)
				h = 50
				d = 8
				w = 100
				glEnable(GL_BLEND)
				glBlendFunc(GL_DST_COLOR, GL_ZERO)
				glBegin(GL_QUADS)
				glTexCoord2f(1, 0)
				glVertex3f( w, 0, h)
				glTexCoord2f(0, 0)
				glVertex3f(-w, 0, h)
				glTexCoord2f(0, 1)
				glVertex3f(-w, 0, 0)
				glTexCoord2f(1, 1)
				glVertex3f( w, 0, 0)

				glTexCoord2f(1, 0)
				glVertex3f(-w, d, h)
				glTexCoord2f(0, 0)
				glVertex3f( w, d, h)
				glTexCoord2f(0, 1)
				glVertex3f( w, d, 0)
				glTexCoord2f(1, 1)
				glVertex3f(-w, d, 0)
				glEnd()
				glDisable(GL_TEXTURE_2D)
				glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
				glPopMatrix()
				
		elif machine.startswith('Witbox'):
			if machine not in self._platformMesh:
				meshes = meshLoader.loadMeshes(resources.getPathForMesh(machine + '_platform.stl'))
				if len(meshes) > 0:
					self._platformMesh[machine] = meshes[0]
				else:
					self._platformMesh[machine] = None
				if machine == 'Witbox':
					self._platformMesh[machine]._drawOffset = numpy.array([0,-37,145], numpy.float32)
			glColor4f(1,1,1,0.5)
			self._objectShader.bind()
			self._renderObject(self._platformMesh[machine], False, False)
			self._objectShader.unbind()
		else:
			glColor4f(0,0,0,1)
			glLineWidth(3)
			glBegin(GL_LINES)
			glVertex3f(-size[0] / 2, -size[1] / 2, 0)
			glVertex3f(-size[0] / 2, -size[1] / 2, 10)
			glVertex3f(-size[0] / 2, -size[1] / 2, 0)
			glVertex3f(-size[0] / 2+10, -size[1] / 2, 0)
			glVertex3f(-size[0] / 2, -size[1] / 2, 0)
			glVertex3f(-size[0] / 2, -size[1] / 2+10, 0)
			glEnd()

		glDepthMask(False)

		polys = profile.getMachineSizePolygons()
		height = profile.getMachineSettingFloat('machine_height')
		circular = profile.getMachineSetting('machine_shape') == 'Circular'
		glBegin(GL_QUADS)
		# Draw the sides of the build volume.
		for n in xrange(0, len(polys[0])):
			if not circular:
				if n % 2 == 0:
					glColor4ub(5, 171, 231, 96)
				else:
					glColor4ub(5, 171, 231, 64)
			else:
				glColor4ub(5, 171, 231, 96)

			glVertex3f(polys[0][n][0], polys[0][n][1], height)
			glVertex3f(polys[0][n][0], polys[0][n][1], 0)
			glVertex3f(polys[0][n-1][0], polys[0][n-1][1], 0)
			glVertex3f(polys[0][n-1][0], polys[0][n-1][1], height)
		glEnd()

		#Draw top of build volume.
		glColor4ub(5, 171, 231, 128)
		glBegin(GL_TRIANGLE_FAN)
		for p in polys[0][::-1]:
			glVertex3f(p[0], p[1], height)
		glEnd()

		#Draw checkerboard
		if self._platformTexture is None:
			self._platformTexture = openglHelpers.loadGLTexture('checkerboard.png')
			glBindTexture(GL_TEXTURE_2D, self._platformTexture)
			glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
			glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
		glColor4f(1,1,1,0.5)
		glBindTexture(GL_TEXTURE_2D, self._platformTexture)
		glEnable(GL_TEXTURE_2D)
		glBegin(GL_TRIANGLE_FAN)
		for p in polys[0]:
			glTexCoord2f(p[0]/20, p[1]/20)
			glVertex3f(p[0], p[1], 0)
		glEnd()

		#Draw no-go zones. (clips in case of UM2)
		glDisable(GL_TEXTURE_2D)
		glColor4ub(127, 127, 127, 200)
		for poly in polys[1:]:
			glBegin(GL_TRIANGLE_FAN)
			for p in poly:
				glTexCoord2f(p[0]/20, p[1]/20)
				glVertex3f(p[0], p[1], 0)
			glEnd()

		glDepthMask(True)
		glDisable(GL_BLEND)
		glDisable(GL_CULL_FACE)

	def getObjectCenterPos(self):
		if self._selectedObj is None:
			return [0.0, 0.0, 0.0]
		pos = self._selectedObj.getPosition()
		size = self._selectedObj.getSize()
		return [pos[0], pos[1], size[2]/2 - profile.getProfileSettingFloat('object_sink')]

	def getObjectBoundaryCircle(self):
		if self._selectedObj is None:
			return 0.0
		return self._selectedObj.getBoundaryCircle()

	def getObjectSize(self):
		if self._selectedObj is None:
			return [0.0, 0.0, 0.0]
		return self._selectedObj.getSize()

	def getObjectMatrix(self):
		if self._selectedObj is None:
			return numpy.matrix(numpy.identity(3))
		return self._selectedObj.getMatrix()

#TODO: Remove this or put it in a seperate file
class shaderEditor(wx.Frame):
	def __init__(self, parent, callback, v, f):
		super(shaderEditor, self).__init__(parent, title="Shader editor", style=wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER)
		self._callback = callback
		s = wx.BoxSizer(wx.VERTICAL)
		self.SetSizer(s)
		self._vertex = wx.TextCtrl(self, -1, v, style=wx.TE_MULTILINE)
		self._fragment = wx.TextCtrl(self, -1, f, style=wx.TE_MULTILINE)
		s.Add(self._vertex, 1, flag=wx.EXPAND)
		s.Add(self._fragment, 1, flag=wx.EXPAND)

		self._vertex.Bind(wx.EVT_TEXT, self.OnText, self._vertex)
		self._fragment.Bind(wx.EVT_TEXT, self.OnText, self._fragment)

		self.SetPosition(self.GetParent().GetPosition())
		self.SetSize((self.GetSize().GetWidth(), self.GetParent().GetSize().GetHeight()))
		self.Show()

	def OnText(self, e):
		self._callback(self._vertex.GetValue(), self._fragment.GetValue())
