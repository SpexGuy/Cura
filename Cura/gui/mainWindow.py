__copyright__ = "Copyright (C) 2013 David Braam - Released under terms of the AGPLv3 License"

import wx
import os
import webbrowser
import sys


from Cura.gui import configBase
from Cura.gui import expertConfig
from Cura.gui import alterationPanel
from Cura.gui import pluginPanel
from Cura.gui import preferencesDialog
from Cura.gui import configWizard
from Cura.gui import firmwareInstall
from Cura.gui import simpleMode
from Cura.gui import sceneView
from Cura.gui import aboutWindow
from Cura.gui.util import dropTarget
#from Cura.gui.tools import batchRun
from Cura.gui.tools import pidDebugger
from Cura.gui.tools import minecraftImport
from Cura.util import profile
from Cura.util import version
import platform
from Cura.util import meshLoader

from wx.lib.pubsub import Publisher

class mainWindow(wx.Frame):
	def __init__(self):
		super(mainWindow, self).__init__(None, title='Cura - ' + version.getVersion())

		wx.EVT_CLOSE(self, self.OnClose)

		# allow dropping any file, restrict later
		self.SetDropTarget(dropTarget.FileDropTarget(self.OnDropFiles))

		# TODO: wxWidgets 2.9.4 has a bug when NSView does not register for dragged types when wx drop target is set. It was fixed in 2.9.5
		if sys.platform.startswith('darwin'):
			try:
				import objc
				nswindow = objc.objc_object(c_void_p=self.MacGetTopLevelWindowRef())
				view = nswindow.contentView()
				view.registerForDraggedTypes_([u'NSFilenamesPboardType'])
			except:
				pass

		self.normalModeOnlyItems = []

		mruFile = os.path.join(profile.getBasePath(), 'mru_filelist.ini')
		self.config = wx.FileConfig(appName="Cura",
						localFilename=mruFile,
						style=wx.CONFIG_USE_LOCAL_FILE)

		self.ID_MRU_MODEL1, self.ID_MRU_MODEL2, self.ID_MRU_MODEL3, self.ID_MRU_MODEL4, self.ID_MRU_MODEL5, self.ID_MRU_MODEL6, self.ID_MRU_MODEL7, self.ID_MRU_MODEL8, self.ID_MRU_MODEL9, self.ID_MRU_MODEL10 = [wx.NewId() for line in xrange(10)]
		self.modelFileHistory = wx.FileHistory(10, self.ID_MRU_MODEL1)
		self.config.SetPath("/ModelMRU")
		self.modelFileHistory.Load(self.config)

		self.ID_MRU_PROFILE1, self.ID_MRU_PROFILE2, self.ID_MRU_PROFILE3, self.ID_MRU_PROFILE4, self.ID_MRU_PROFILE5, self.ID_MRU_PROFILE6, self.ID_MRU_PROFILE7, self.ID_MRU_PROFILE8, self.ID_MRU_PROFILE9, self.ID_MRU_PROFILE10 = [wx.NewId() for line in xrange(10)]
		self.profileFileHistory = wx.FileHistory(10, self.ID_MRU_PROFILE1)
		self.config.SetPath("/ProfileMRU")
		self.profileFileHistory.Load(self.config)

		self.menubar = wx.MenuBar()
		self.fileMenu = wx.Menu()
		i = self.fileMenu.Append(-1, _("Load model file...\tCTRL+L"))
		self.Bind(wx.EVT_MENU, lambda e: self.scene.showLoadModel(), i)

		# Model MRU list
		modelHistoryMenu = wx.Menu()
		self.fileMenu.AppendMenu(wx.NewId(), '&' + _("Recent Model Files"), modelHistoryMenu)
		self.modelFileHistory.UseMenu(modelHistoryMenu)
		self.modelFileHistory.AddFilesToMenu()
		self.Bind(wx.EVT_MENU_RANGE, self.OnModelMRU, id=self.ID_MRU_MODEL1, id2=self.ID_MRU_MODEL10)

		i = self.fileMenu.Append(-1, _("Save model...\tCTRL+S"))
		self.Bind(wx.EVT_MENU, lambda e: self.scene.showSaveModel(), i)
		i = self.fileMenu.Append(-1, _("Reload platform\tF5"))
		self.Bind(wx.EVT_MENU, lambda e: self.scene.reloadScene(e), i)
		i = self.fileMenu.Append(-1, _("Clear platform"))
		self.Bind(wx.EVT_MENU, lambda e: self.scene.OnDeleteAll(e), i)

		if minecraftImport.hasMinecraft():
			i = self.fileMenu.Append(-1, _("Minecraft map import..."))
			self.Bind(wx.EVT_MENU, self.OnMinecraftImport, i)

		#self.fileMenu.AppendSeparator()
		#TODO: filter these options
		#i = self.fileMenu.Append(-1, _("Open Profile..."))
		#self.normalModeOnlyItems.append(i)
		#self.Bind(wx.EVT_MENU, self.OnLoadProfile, i)
		#i = self.fileMenu.Append(-1, _("Save Profile..."))
		#self.normalModeOnlyItems.append(i)
		#self.Bind(wx.EVT_MENU, self.OnSaveProfile, i)
		#self.fileMenu.AppendSeparator()
		#i = self.fileMenu.Append(-1, _("Reset Profile to default"))
		#self.normalModeOnlyItems.append(i)
		#self.Bind(wx.EVT_MENU, self.OnResetProfile, i)

#		self.fileMenu.AppendSeparator()
#		i = self.fileMenu.Append(-1, _("Preferences...\tCTRL+,"))
#		self.Bind(wx.EVT_MENU, self.OnPreferences, i)
#		self.fileMenu.AppendSeparator()

		# Profle MRU list
		#profileHistoryMenu = wx.Menu()
		#self.fileMenu.AppendMenu(wx.NewId(), _("Recent Profile Files"), profileHistoryMenu)
		#self.profileFileHistory.UseMenu(profileHistoryMenu)
		#self.profileFileHistory.AddFilesToMenu()
		#self.Bind(wx.EVT_MENU_RANGE, self.OnProfileMRU, id=self.ID_MRU_PROFILE1, id2=self.ID_MRU_PROFILE10)

		self.fileMenu.AppendSeparator()
		i = self.fileMenu.Append(wx.ID_EXIT, _("Quit"))
		self.Bind(wx.EVT_MENU, self.OnQuit, i)
		self.menubar.Append(self.fileMenu, '&' + _("File"))

		#i = toolsMenu.Append(-1, 'Batch run...')
		#self.Bind(wx.EVT_MENU, self.OnBatchRun, i)
		#self.normalModeOnlyItems.append(i)


		if version.isDevVersion():
			toolsMenu = wx.Menu()
			i = toolsMenu.Append(-1, _("PID Debugger..."))
			self.Bind(wx.EVT_MENU, self.OnPIDDebugger, i)
			self.menubar.Append(toolsMenu, _("Debug"))

#		expertMenu = wx.Menu()
#		i = expertMenu.Append(-1, _("Open expert settings...\tCTRL+E"))
#		self.normalModeOnlyItems.append(i)
#		self.Bind(wx.EVT_MENU, self.OnExpertOpen, i)
#		expertMenu.AppendSeparator()
#		i = expertMenu.Append(-1, _("Run first run wizard..."))
#		self.Bind(wx.EVT_MENU, self.OnFirstRunWizard, i)

#		self.menubar.Append(expertMenu, _("Expert"))

		helpMenu = wx.Menu()
		i = helpMenu.Append(-1, _("Online documentation..."))
		self.Bind(wx.EVT_MENU, lambda e: webbrowser.open('http://daid.github.com/Cura'), i)
		i = helpMenu.Append(-1, _("Report a problem..."))
		self.Bind(wx.EVT_MENU, lambda e: webbrowser.open('https://github.com/daid/Cura/issues'), i)
		i = helpMenu.Append(-1, _("Check for update..."))
		self.Bind(wx.EVT_MENU, self.OnCheckForUpdate, i)
		i = helpMenu.Append(-1, _("Open YouMagine website..."))
		self.Bind(wx.EVT_MENU, lambda e: webbrowser.open('https://www.youmagine.com/'), i)
		i = helpMenu.Append(-1, _("About Cura..."))
		self.Bind(wx.EVT_MENU, self.OnAbout, i)
		self.menubar.Append(helpMenu, _("Help"))
		self.SetMenuBar(self.menubar)


		self.rightPane = wx.Panel(self, style=wx.BORDER_NONE)

		##Gui components##
		#Preview window
		self.scene = sceneView.SceneView(self.rightPane)

		#Main sizer, to position the preview window, buttons and tab control
		sizer = wx.BoxSizer()
		self.rightPane.SetSizer(sizer)
		sizer.Add(self.scene, 1, flag=wx.EXPAND)

		# Main window sizer
		sizer = wx.BoxSizer(wx.VERTICAL)
		self.SetSizer(sizer)
		sizer.Add(self.rightPane, 1, wx.EXPAND)
		sizer.Layout()
		self.sizer = sizer

		self.updateProfileToAllControls()

		# Set default window size & position
		self.SetSize((wx.Display().GetClientArea().GetWidth()/2,wx.Display().GetClientArea().GetHeight()/2))
		self.Centre()

		#Timer set; used to check if profile is on the clipboard
		self.timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self.onTimer)
		self.timer.Start(1000)
		self.lastTriedClipboard = profile.getProfileString()

		# Restore the window position, size & state from the preferences file
		try:
			if profile.getPreference('window_maximized') == 'True':
				self.Maximize(True)
			else:
				posx = int(profile.getPreference('window_pos_x'))
				posy = int(profile.getPreference('window_pos_y'))
				width = int(profile.getPreference('window_width'))
				height = int(profile.getPreference('window_height'))
				if posx > 0 or posy > 0:
					self.SetPosition((posx,posy))
				if width > 0 and height > 0:
					self.SetSize((width,height))

		except:
			self.Maximize(True)

		if wx.Display.GetFromPoint(self.GetPosition()) < 0:
			self.Centre()
		if wx.Display.GetFromPoint((self.GetPositionTuple()[0] + self.GetSizeTuple()[1], self.GetPositionTuple()[1] + self.GetSizeTuple()[1])) < 0:
			self.Centre()
		if wx.Display.GetFromPoint(self.GetPosition()) < 0:
			self.SetSize((800,600))
			self.Centre()

		self.updateSliceMode()
		self.scene.SetFocus()
		self.dialogframe = None
		Publisher().subscribe(self.onPluginUpdate, "pluginupdate")

	def onPluginUpdate(self,msg): #receives commands from the plugin thread
		cmd = str(msg.data).split(";")
		if cmd[0] == "OpenPluginProgressWindow":
			if len(cmd)==1: #no titel received
				cmd.append("Plugin")
			if len(cmd)<3: #no message text received
				cmd.append("Plugin is executed...")
			dialogwidth = 300
			dialogheight = 80
			self.dialogframe = wx.Frame(self, -1, cmd[1],pos = ((wx.SystemSettings.GetMetric(wx.SYS_SCREEN_X)-dialogwidth)/2,(wx.SystemSettings.GetMetric(wx.SYS_SCREEN_Y)-dialogheight)/2), size=(dialogwidth,dialogheight), style = wx.STAY_ON_TOP)
			self.dialogpanel = wx.Panel(self.dialogframe, -1, pos = (0,0), size = (dialogwidth,dialogheight))
			self.dlgtext = wx.StaticText(self.dialogpanel, label = cmd[2], pos = (10,10), size = (280,40))
			self.dlgbar = wx.Gauge(self.dialogpanel,-1, 100, pos = (10,50), size = (280,20), style = wx.GA_HORIZONTAL)
			self.dialogframe.Show()

		elif cmd[0] == "Progress":
			number = int(cmd[1])
			if number <= 100 and self.dialogframe is not None:
				self.dlgbar.SetValue(number)
			else:
				self.dlgbar.SetValue(100)
		elif cmd[0] == "ClosePluginProgressWindow":
			self.dialogframe.Destroy()
			self.dialogframe=None
		else:
			print "Unknown Plugin update received: " + cmd[0]

	def onTimer(self, e):
		#Check if there is something in the clipboard
		profileString = ""
		try:
			if not wx.TheClipboard.IsOpened():
				if not wx.TheClipboard.Open():
					return
				do = wx.TextDataObject()
				if wx.TheClipboard.GetData(do):
					profileString = do.GetText()
				wx.TheClipboard.Close()

				startTag = "CURA_PROFILE_STRING:"
				if startTag in profileString:
					#print "Found correct syntax on clipboard"
					profileString = profileString.replace("\n","").strip()
					profileString = profileString[profileString.find(startTag)+len(startTag):]
					if profileString != self.lastTriedClipboard:
						print profileString
						self.lastTriedClipboard = profileString
						profile.setProfileFromString(profileString)
						self.scene.notification.message("Loaded new profile from clipboard.")
						self.updateProfileToAllControls()
		except:
			print "Unable to read from clipboard"


	def updateSliceMode(self):
		isSimple = profile.getPreference('startMode') == 'Simple'

		for i in self.normalModeOnlyItems:
			i.Enable(not isSimple)

		self.scene.updateProfileToControls()
		self.scene._scene.pushFree()

	def OnPreferences(self, e):
		prefDialog = preferencesDialog.preferencesDialog(self)
		prefDialog.Centre()
		prefDialog.Show()
		prefDialog.Raise()
		wx.CallAfter(prefDialog.Show)

	def OnDropFiles(self, files):
		if len(files) > 0:
			self.updateProfileToAllControls()
		self.scene.loadFiles(files)

	def OnModelMRU(self, e):
		fileNum = e.GetId() - self.ID_MRU_MODEL1
		path = self.modelFileHistory.GetHistoryFile(fileNum)
		# Update Model MRU
		self.modelFileHistory.AddFileToHistory(path)  # move up the list
		self.config.SetPath("/ModelMRU")
		self.modelFileHistory.Save(self.config)
		self.config.Flush()
		# Load Model
		profile.putPreference('lastFile', path)
		filelist = [ path ]
		self.scene.loadFiles(filelist)

	def addToModelMRU(self, file):
		self.modelFileHistory.AddFileToHistory(file)
		self.config.SetPath("/ModelMRU")
		self.modelFileHistory.Save(self.config)
		self.config.Flush()

	def OnProfileMRU(self, e):
		fileNum = e.GetId() - self.ID_MRU_PROFILE1
		path = self.profileFileHistory.GetHistoryFile(fileNum)
		# Update Profile MRU
		self.profileFileHistory.AddFileToHistory(path)  # move up the list
		self.config.SetPath("/ProfileMRU")
		self.profileFileHistory.Save(self.config)
		self.config.Flush()
		# Load Profile
		profile.loadProfile(path)
		self.updateProfileToAllControls()

	def addToProfileMRU(self, file):
		self.profileFileHistory.AddFileToHistory(file)
		self.config.SetPath("/ProfileMRU")
		self.profileFileHistory.Save(self.config)
		self.config.Flush()

	def updateProfileToAllControls(self):
		self.scene.updateProfileToControls()

	def reloadSettingPanels(self):
		self.updateSliceMode()
		self.updateProfileToAllControls()

	def OnLoadProfile(self, e):
		dlg=wx.FileDialog(self, _("Select profile file to load"), os.path.split(profile.getPreference('lastFile'))[0], style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST)
		dlg.SetWildcard("ini files (*.ini)|*.ini")
		if dlg.ShowModal() == wx.ID_OK:
			profileFile = dlg.GetPath()
			profile.loadProfile(profileFile)
			self.updateProfileToAllControls()

			# Update the Profile MRU
			self.addToProfileMRU(profileFile)
		dlg.Destroy()

	def OnLoadProfileFromGcode(self, e):
		dlg=wx.FileDialog(self, _("Select gcode file to load profile from"), os.path.split(profile.getPreference('lastFile'))[0], style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST)
		dlg.SetWildcard("gcode files (*%s)|*%s;*%s" % (profile.getGCodeExtension(), profile.getGCodeExtension(), profile.getGCodeExtension()[0:2]))
		if dlg.ShowModal() == wx.ID_OK:
			gcodeFile = dlg.GetPath()
			f = open(gcodeFile, 'r')
			hasProfile = False
			for line in f:
				if line.startswith(';CURA_PROFILE_STRING:'):
					profile.setProfileFromString(line[line.find(':')+1:].strip())
					if ';{profile_string}' not in profile.getAlterationFile('end.gcode'):
						profile.setAlterationFile('end.gcode', profile.getAlterationFile('end.gcode') + '\n;{profile_string}')
					hasProfile = True
			if hasProfile:
				self.updateProfileToAllControls()
			else:
				wx.MessageBox(_("No profile found in GCode file.\nThis feature only works with GCode files made by Cura 12.07 or newer."), _("Profile load error"), wx.OK | wx.ICON_INFORMATION)
		dlg.Destroy()

	def OnSaveProfile(self, e):
		dlg=wx.FileDialog(self, _("Select profile file to save"), os.path.split(profile.getPreference('lastFile'))[0], style=wx.FD_SAVE)
		dlg.SetWildcard("ini files (*.ini)|*.ini")
		if dlg.ShowModal() == wx.ID_OK:
			profileFile = dlg.GetPath()
			if not profileFile.lower().endswith('.ini'): #hack for linux, as for some reason the .ini is not appended.
				profileFile += '.ini'
			profile.saveProfile(profileFile)
		dlg.Destroy()

	def OnResetProfile(self, e):
		dlg = wx.MessageDialog(self, _("This will reset all profile settings to defaults.\nUnless you have saved your current profile, all settings will be lost!\nDo you really want to reset?"), _("Profile reset"), wx.YES_NO | wx.ICON_QUESTION)
		result = dlg.ShowModal() == wx.ID_YES
		dlg.Destroy()
		if result:
			profile.resetProfile()
			self.updateProfileToAllControls()

	def OnFirstRunWizard(self, e):
		self.Hide()
		configWizard.configWizard()
		self.Show()
		self.reloadSettingPanels()

	def OnExpertOpen(self, e):
		ecw = expertConfig.expertConfigWindow(lambda : self.scene.sceneUpdated())
		ecw.Centre()
		ecw.Show()

	def OnMinecraftImport(self, e):
		mi = minecraftImport.minecraftImportWindow(self)
		mi.Centre()
		mi.Show(True)

	def OnPIDDebugger(self, e):
		debugger = pidDebugger.debuggerWindow(self)
		debugger.Centre()
		debugger.Show(True)

	def onCopyProfileClipboard(self, e):
		try:
			if not wx.TheClipboard.IsOpened():
				wx.TheClipboard.Open()
				clipData = wx.TextDataObject()
				self.lastTriedClipboard = profile.getProfileString()
				profileString = profile.insertNewlines("CURA_PROFILE_STRING:" + self.lastTriedClipboard)
				clipData.SetText(profileString)
				wx.TheClipboard.SetData(clipData)
				wx.TheClipboard.Close()
		except:
			print "Could not write to clipboard, unable to get ownership. Another program is using the clipboard."

	def OnCheckForUpdate(self, e):
		newVersion = version.checkForNewerVersion()
		if newVersion is not None:
			if wx.MessageBox(_("A new version of Cura is available, would you like to download?"), _("New version available"), wx.YES_NO | wx.ICON_INFORMATION) == wx.YES:
				webbrowser.open(newVersion)
		else:
			wx.MessageBox(_("You are running the latest version of Cura!"), _("Awesome!"), wx.ICON_INFORMATION)

	def OnAbout(self, e):
		aboutBox = aboutWindow.aboutWindow()
		aboutBox.Centre()
		aboutBox.Show()

	def OnClose(self, e):
		profile.saveProfile(profile.getDefaultProfilePath(), True)

		# Save the window position, size & state from the preferences file
		profile.putPreference('window_maximized', self.IsMaximized())
		if not self.IsMaximized() and not self.IsIconized():
			(posx, posy) = self.GetPosition()
			profile.putPreference('window_pos_x', posx)
			profile.putPreference('window_pos_y', posy)
			(width, height) = self.GetSize()
			profile.putPreference('window_width', width)
			profile.putPreference('window_height', height)

		#HACK: Set the paint function of the glCanvas to nothing so it won't keep refreshing. Which can keep wxWidgets from quiting.
		print "Closing down"
		self.scene.OnPaint = lambda e : e
		self.scene._engine.cleanup()
		self.Destroy()

	def OnQuit(self, e):
		self.Close()
