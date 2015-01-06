__copyright__ = "Copyright (C) 2015 Spectrom - Released under terms of the AGPLv3 License"

import wx
import threading
import time
import re
import os
import types
import webbrowser
import urllib2
import cStringIO as StringIO

from Cura.util import profile
from Cura.util import spectromUpload
from Cura.util.meshLoaders import stl
from Cura.util.meshLoaders import amf
from Cura.util.resources import getPathForImage

DESIGN_FILE_EXT = ['.scad', '.blend', '.max', '.stp', '.step', '.igs', '.iges', '.sldasm', '.sldprt', '.skp', '.iam', '.prt', '.x_t', '.ipt', '.dwg', '.123d', '.wings', '.fcstd', '.top']
EMAIL_RE = re.compile(r"^[-!#$%&'*+/0-9=?A-Z^_a-z{|}~](\.?[-!#$%&'*+/0-9=?A-Z^_a-z{|}~])*@[a-zA-Z](-?[a-zA-Z0-9])*(\.[a-zA-Z](-?[a-zA-Z0-9])*)+$")

def getClipboardText():
	ret = ''
	try:
		if not wx.TheClipboard.IsOpened():
			wx.TheClipboard.Open()
			do = wx.TextDataObject()
			if wx.TheClipboard.GetData(do):
				ret = do.GetText()
			wx.TheClipboard.Close()
		return ret
	except:
		return ret

class spectromUploadManager(object):
	def __init__(self, parent, objectScene, colors, forceSetup=False):
		self._mainWindow = parent
		self._scene = objectScene
		self._su = spectromUpload.SpectromUpload(self._progressCallback)
		self._colorString = colors
		self._forceSetup = forceSetup

		self._indicatorWindow = workingIndicatorWindow(self._mainWindow)
		self._newDesignWindow = newDesignWindow(self._mainWindow, self, self._su)

		try:
			licenseInfo = self._su.newLicenseURL()
			if licenseInfo is not None:
				termsWindow = termsAndConditionsWindow(self._mainWindow, licenseInfo[0], licenseInfo[1], self.OnLicenseAccepted)
				termsWindow.Show()
			else:
				self.OnLicenseAccepted()
		except:
			import traceback
			traceback.print_exc()
			wx.MessageBox(_("Couldn't connect to Spectrom.\nIf the problem persists, contact\norders@spectrom3d.com"), _("Can't contact Spectrom"), wx.OK | wx.ICON_ERROR)
			return

	def OnLicenseAccepted(self):
		if self._forceSetup or not profile.getPreference('spectrom_email'):
			self._configWindow = configureWindow(self._mainWindow, self.OnEmailEntered)
			self._configWindow.Show()
		else:
			self._newDesignWindow.Show()

	def OnEmailEntered(self):
		self._newDesignWindow.Show()

	def _progressCallback(self, progress):
		self._indicatorWindow.progress(progress)

	def createNewOrder(self, name):
		thread = threading.Thread(target=self.createNewOrderThread, args=(name,))
		thread.daemon = True
		thread.start()

	def createNewOrderThread(self, name):
		wx.CallAfter(self._indicatorWindow.showBusy, _("Uploading models..."))
		order = self._su.postOrder(name, self._scene.objects(), self._colorString)
		wx.CallAfter(self._indicatorWindow.Hide)

		#TODO: link to view orders
		if order is not None:
			wx.CallAfter(wx.MessageBox, _("Upload Successful!\nYour order identifier is\n") + str(order) , _("File Uploaded."), wx.OK)
		else:
			wx.CallAfter(wx.MessageBox, _("Upload Failed! If the problem persists, contact orders@spectrom3d.com"), _("Upload error."), wx.OK | wx.ICON_ERROR)

		#webbrowser.open(self._su.viewUrlForDesign(id))

class termsAndConditionsWindow(wx.Frame):
	def __init__(self, parent, termsUrl, termsVersion, callback):
		super(termsAndConditionsWindow, self).__init__(parent, title='End User License Agreement - Version %s' % (termsVersion), style=wx.FRAME_TOOL_WINDOW|wx.FRAME_FLOAT_ON_PARENT|wx.FRAME_NO_TASKBAR|wx.CAPTION)
		self._callback = callback
		self._version = termsVersion
		licenseFile = urllib2.urlopen(termsUrl)
		licenseText = licenseFile.read()
		licenseFile.close()

		panel = wx.Panel(self, wx.ID_ANY)
		terms = wx.TextCtrl(panel, wx.ID_ANY, size=(300,100), style = wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
		buttonPanel = wx.Panel(panel, wx.ID_ANY)
		acceptButton = wx.Button(buttonPanel, wx.ID_ANY, 'Accept')
		cancelButton = wx.Button(buttonPanel, wx.ID_ANY, 'Cancel')

		self.Bind(wx.EVT_BUTTON, self.OnAccept, acceptButton)
		self.Bind(wx.EVT_BUTTON, self.OnCancel, cancelButton)

		sizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(cancelButton, 1, wx.ALL | wx.RIGHT, 5)
		sizer.Add(acceptButton, 1, wx.ALL | wx.RIGHT, 5)
		buttonPanel.SetSizer(sizer)

		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(terms, 1, wx.ALL | wx.EXPAND, 5)
		sizer.Add(buttonPanel, 0, wx.ALL | wx.EXPAND, 0)
		panel.SetSizer(sizer)

		terms.SetValue(licenseText)

	def OnCancel(self, e):
		wx.MessageBox(_('You must accept the terms to use the Spectrom Order Service'), _(''), wx.OK)
		self.Hide()
		self.Dispose()

	def OnAccept(self, e):
		profile.putPreference('spectrom_terms_version', self._version)
		self._callback()
		self.Hide()
		self.Dispose()


class workingIndicatorWindow(wx.Frame):
	def __init__(self, parent):
		super(workingIndicatorWindow, self).__init__(parent, title='Spectrom', style=wx.FRAME_TOOL_WINDOW|wx.FRAME_FLOAT_ON_PARENT|wx.FRAME_NO_TASKBAR|wx.CAPTION)
		self._panel = wx.Panel(self)
		self.SetSizer(wx.BoxSizer())
		self.GetSizer().Add(self._panel, 1, wx.EXPAND)

		self._busyBitmaps = [
			wx.Bitmap(getPathForImage('busy-0.png')),
			wx.Bitmap(getPathForImage('busy-1.png')),
			wx.Bitmap(getPathForImage('busy-2.png')),
			wx.Bitmap(getPathForImage('busy-3.png'))
		]

		self._indicatorBitmap = wx.StaticBitmap(self._panel, -1, wx.EmptyBitmapRGBA(24, 24, red=255, green=255, blue=255, alpha=1))
		self._statusText = wx.StaticText(self._panel, -1, '...')
		self._progress = wx.Gauge(self._panel, -1)
		self._progress.SetRange(1000)
		self._progress.SetMinSize((250, 30))

		self._panel._sizer = wx.GridBagSizer(2, 2)
		self._panel.SetSizer(self._panel._sizer)
		self._panel._sizer.Add(self._indicatorBitmap, (0, 0), flag=wx.ALL, border=5)
		self._panel._sizer.Add(self._statusText, (0, 1), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=5)
		self._panel._sizer.Add(self._progress, (1, 0), span=(1,2), flag=wx.EXPAND|wx.ALL, border=5)

		self._busyState = 0
		self._busyTimer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self._busyUpdate, self._busyTimer)
		self._busyTimer.Start(100)

	def _busyUpdate(self, e):
		if self._busyState is None:
			return
		self._busyState += 1
		if self._busyState >= len(self._busyBitmaps):
			self._busyState = 0
		self._indicatorBitmap.SetBitmap(self._busyBitmaps[self._busyState])

	def progress(self, progressAmount):
		wx.CallAfter(self._progress.Show)
		wx.CallAfter(self._progress.SetValue, progressAmount*1000)
		wx.CallAfter(self.Layout)
		wx.CallAfter(self.Fit)

	def showBusy(self, text):
		self._statusText.SetLabel(text)
		self._progress.Hide()
		self.Layout()
		self.Fit()
		self.Centre()
		self.Show()

class configureWindow(wx.Frame):
	def __init__(self, parent, callback):
		super(configureWindow, self).__init__(parent, title='Spectrom Profile')
		self._panel = wx.Panel(self)
		self.SetSizer(wx.BoxSizer())
		self.GetSizer().Add(self._panel, 1, wx.EXPAND)
		self._callback = callback
		self.abort = False

		self._firstName = wx.TextCtrl(self._panel, -1, profile.getPreference("spectrom_firstname") or _("First Name"))
		self._lastName = wx.TextCtrl(self._panel, -1, profile.getPreference("spectrom_lastname") or _("Last Name"))
		self._emailAddress = wx.TextCtrl(self._panel, -1, profile.getPreference("spectrom_email") or _("Email"))
		self._companyName = wx.TextCtrl(self._panel, -1, profile.getPreference("spectrom_companyname") or _("Company (optional)"))
		self._doneButton = wx.Button(self._panel, -1, _("Submit"))

		self._panel._sizer = wx.GridBagSizer(5, 5)
		self._panel.SetSizer(self._panel._sizer)

		self._panel._sizer.Add(wx.StaticBitmap(self._panel, -1, wx.Bitmap(getPathForImage('youmagine-text.png'))), (0,0), span=(1,4), flag=wx.ALIGN_CENTRE | wx.ALL, border=5)
		self._panel._sizer.Add(wx.StaticLine(self._panel, -1), (1,0), span=(1,4), flag=wx.EXPAND | wx.ALL)
		self._panel._sizer.Add(self._firstName, (2, 1), flag=wx.EXPAND | wx.ALL)
		self._panel._sizer.Add(self._lastName, (3, 1), flag=wx.EXPAND | wx.ALL)
		self._panel._sizer.Add(self._emailAddress, (4, 1), flag=wx.EXPAND | wx.ALL)
		self._panel._sizer.Add(self._companyName, (5, 1), flag=wx.EXPAND | wx.ALL)
		self._panel._sizer.Add(wx.StaticLine(self._panel, -1), (6,0), span=(1,4), flag=wx.EXPAND | wx.ALL)
		self._panel._sizer.Add(self._doneButton, (7, 1), flag=wx.EXPAND | wx.ALL)

		self.Bind(wx.EVT_TEXT, self.OnEnterEmail, self._emailAddress)
		self.Bind(wx.EVT_TEXT, self.OnEnterFirst, self._firstName)
		self.Bind(wx.EVT_TEXT, self.OnEnterLast, self._lastName)
		self.Bind(wx.EVT_BUTTON, self.OnSubmit, self._doneButton)

		self.Fit()
		self.Centre()

		self._firstName.SetFocus()
		self._firstName.SelectAll()

	def OnEnterEmail(self, e):
		self._emailAddress.SetBackgroundColour(wx.NullColor)

	def OnEnterFirst(self, e):
		self._firstName.SetBackgroundColour(wx.NullColor)

	def OnEnterLast(self, e):
		self._lastName.SetBackgroundColour(wx.NullColor)

	def OnSubmit(self, e):
		passed = True;
		first = self._firstName.GetValue().strip()
		last = self._lastName.GetValue().strip()
		email = self._emailAddress.GetValue().strip()
		if not first or ' ' in first:
			self._firstName.SetBackgroundColour("red")
			passed = False;
		if not last or ' ' in last:
			self._lastName.SetBackgroundColour("red")
			passed = False;
		if not EMAIL_RE.match(email):
			self._emailAddress.SetBackgroundColour("red")
			passed = False;
		
		if passed:
			profile.putPreference('spectrom_firstname', first)
			profile.putPreference('spectrom_lastname', last)
			profile.putPreference('spectrom_email', email)
			company = self._companyName.GetValue().strip()
			if company != _("Company (optional)"):
				profile.putPreference('spectrom_companyname', company)
			self._callback()
			self.Hide()
			self.Dispose()

class newDesignWindow(wx.Frame):
	def __init__(self, parent, manager, su):
		super(newDesignWindow, self).__init__(parent, title='Order from Spectrom')
		p = wx.Panel(self)
		self.SetSizer(wx.BoxSizer())
		self.GetSizer().Add(p, 1, wx.EXPAND)
		self._manager = manager
		self._su = su

		self._designName = wx.TextCtrl(p, -1, _("Design name"))
		self._shareButton = wx.Button(p, -1, _("Share!"))

		s = wx.GridBagSizer(5, 5)
		p.SetSizer(s)

		s.Add(wx.StaticBitmap(p, -1, wx.Bitmap(getPathForImage('youmagine-text.png'))), (0,0), span=(1,3), flag=wx.ALIGN_CENTRE | wx.ALL, border=5)
		s.Add(wx.StaticText(p, -1, _("Design name:")), (1, 0), flag=wx.LEFT|wx.TOP, border=5)
		s.Add(self._designName, (1, 1), span=(1,2), flag=wx.EXPAND|wx.LEFT|wx.TOP|wx.RIGHT, border=5)
		s.Add(wx.StaticLine(p, -1), (2,0), span=(1,3), flag=wx.EXPAND|wx.ALL)
		s.Add(self._shareButton, (3, 1), flag=wx.BOTTOM, border=15)

		self.Bind(wx.EVT_BUTTON, self.OnShare, self._shareButton)

		self.Fit()
		self.Centre()

		self._designName.SetFocus()
		self._designName.SelectAll()

	def OnShare(self, e):
		if self._designName.GetValue() == '':
			wx.MessageBox(_("The name cannot be empty"), _("New design error."), wx.OK | wx.ICON_ERROR)
			self._designName.SetFocus()
			return
		self._manager.createNewOrder(self._designName.GetValue())
		self.Destroy()
