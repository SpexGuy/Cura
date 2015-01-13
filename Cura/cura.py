#!/usr/bin/python
"""
This page is in the table of contents.
==Overview==
===Introduction===
Cura is a AGPL tool chain to generate a GCode path for 3D printing. Older versions of Cura where based on Skeinforge.
Versions up from 13.05 are based on a C++ engine called CuraEngine.
"""
__copyright__ = "Copyright (C) 2013 David Braam - Released under terms of the AGPLv3 License"

from optparse import OptionParser

from Cura.util import profile

def main():
	"""
	Main Cura entry point. Parses arguments, loads profile, and starts GUI.
	"""
	parser = OptionParser(usage="usage: %prog [options] <filename>.stl")
	parser.add_option("-i", "--ini", action="store", type="string", dest="profileini",
		help="Load settings from a profile ini file")
	parser.add_option("-p", "--profile", action="store", type="string", dest="profile",
		help="Internal option, do not use!")
	parser.add_option("-s", "--slice", action="store_true", dest="slice",
		help="Slice the given files instead of opening them in Cura")
	parser.add_option("-o", "--output", action="store", type="string", dest="output",
		help="path to write sliced file to")

	(options, args) = parser.parse_args()

	print "load preferences from " + profile.getPreferencePath()
	profile.loadPreferences(profile.getPreferencePath())

	if options.profile is not None:
		profile.setProfileFromString(options.profile)
	elif options.profileini is not None:
		profile.loadProfile(options.profileini)
	else:
		profile.loadProfile(profile.getDefaultProfilePath(), True)

	if options.slice is not None:
		from Cura.util import sliceEngine
		from Cura.util import objectScene
		from Cura.util import meshLoader
		import shutil

		def commandlineProgressCallback(progress):
			if progress >= 0:
				#print 'Preparing: %d%%' % (progress * 100)
				pass
		scene = objectScene.Scene()
		scene.updateMachineDimensions()
		engine = sliceEngine.Engine(commandlineProgressCallback)
		for m in meshLoader.loadMeshes(args[0]):
			scene.add(m)
		engine.runEngine(scene)
		engine.wait()

		if not options.output:
			options.output = args[0] + profile.getGCodeExtension()
		with open(options.output, "wb") as f:
			gcode = engine.getResult().getGCode()
			while True:
				data = gcode.read()
				if len(data) == 0:
					break
				f.write(data)
		print 'GCode file saved : %s' % options.output

		engine.cleanup()
	else:
		from Cura.gui import app
		app.CuraApp(args).MainLoop()

if __name__ == '__main__':
	main()
