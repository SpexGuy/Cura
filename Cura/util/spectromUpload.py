"""
Spectrom communication module.
This module handles all communication with the Spectrom Order API.
"""
__copyright__ = "Copyright (C) 2015 Spectrom - Released under terms of the AGPLv3 License"

import json
import httplib as httpclient
import urllib
import textwrap

from Cura.util import profile
from Cura.util.meshLoaders import stl

#stl.saveSceneStream(httpUploadDataStream, objects)

class httpUploadDataStream(object):
	"""
	For http uploads we need a readable/writable datasteam to use with the httpclient.HTTPSConnection class.
	This is used to facilitate file uploads towards Spectrom.
	"""
	def __init__(self, progressCallback):
		self._dataList = []
		self._totalLength = 0
		self._readPos = 0
		self._progressCallback = progressCallback

	def write(self, data):
		if isinstance(data, httpUploadDataStream):
			for datum in data._dataList:
				self._dataList.append(datum)
				self._totalLength += len(datum)
		else:
			size = len(data)
			if size < 1:
				return
			blocks = size / 2048
			for n in xrange(0, blocks):
				self._dataList.append(data[n*2048:n*2048+2048])
			self._dataList.append(data[blocks*2048:])
			self._totalLength += size

	def read(self, size):
		if self._readPos >= len(self._dataList):
			return None
		ret = self._dataList[self._readPos]
		self._readPos += 1
		if self._progressCallback is not None:
			self._progressCallback(float(self._readPos) / len(self._dataList))
		return ret

	def __len__(self):
		return self._totalLength

class SpectromUpload(object):
	"""
	SpectromUpload connection object. Has various functions to communicate with Spectrom.
	These functions are blocking and thus this class should be used from a thread.
	"""
	def __init__(self, progressCallback = None):
		self._hostUrl = '104.236.72.226:8080'
		#self._hostUrl = '104.236.72.226:80'
		#self._hostUrl = 'localhost:8080'
		self._viewUrl = 'www.spectrom3D.com'
		self._http = None
		self._hostReachable = True
		self._progressCallback = progressCallback

	def isHostReachable(self):
		return self._hostReachable

	def postOrder(self, name, objects, colorProfile):
		params = {
			'firstName': profile.getPreference('spectrom_firstname'),
			'lastName': profile.getPreference('spectrom_lastname'),
			'email': profile.getPreference('spectrom_email'),
			'orderName': name}
		company = profile.getPreference('spectrom_companyname')
		if company:
			params['companyName'] = company

		stream = httpUploadDataStream(lambda progress: None)
		stl.saveSceneStream(stream, objects)

		files = {
			'stlFile': ('order.stl', stream),
			'spectromFile': ('color.spectrom', colorProfile)
		}
		res = self._request('POST', '/order', params, files)
		print res
		if 'orderId' in res:
			return res['orderId']
		return None

	def _request(self, method, url, postData = None, files = None):
		retryCount = 2
		if postData:
			url += '?' + urllib.urlencode(postData)
		error = 'Failed to connect to %s' % self._hostUrl
		for n in xrange(0, retryCount):
			if self._http is None:
				self._http = httpclient.HTTPConnection(self._hostUrl)
			try:
				if files is not None:
					print "-------------- PREPARING REQUEST ---------------"
					boundary = 'wL36Yn8afVp8Ag7AmP8qZ0SA4n1v9T'
					s = httpUploadDataStream(self._progressCallback)
					for k, v in files.iteritems():
						filename = v[0]
						fileContents = v[1]
						s.write('--%s\r\n' % (boundary))
						s.write('Content-Disposition: form-data; name="%s"; filename="%s"\r\n' % (k, filename))
						s.write('Content-Type: application/octet-stream\r\n')
						s.write('Content-Transfer-Encoding: binary\r\n')
						s.write('\r\n')
						s.write(fileContents)
						s.write('\r\n')

					s.write('--%s--\r\n' % (boundary))

					print "------------- SENDING REQUEST ----------------"
					self._http.request(method, url, s, {"Content-type": "multipart/form-data; boundary=%s" % (boundary), "Content-Length": len(s)})
				elif postData is not None:
					self._http.request(method, url, '', {"Content-type": "application/x-www-form-urlencoded"})
				else:
					self._http.request(method, url)
			except IOError, e:
				print e
				import traceback
				traceback.print_exc()
				self._http.close()
				continue
			try:
				print "-------------- WAIT FOR RESPONSE ----------------"
				response = self._http.getresponse()
				responseText = response.read()
			except:
				self._http.close()
				continue
			try:
				if responseText == '':
					return None
				return json.loads(responseText)
			except ValueError:
				print response.getheaders()
				print responseText
				error = 'Failed to decode JSON response'
		self._hostReachable = False
		return {'error': error}


class FakeSpectromUpload(SpectromUpload):
	"""
	Fake SpectromUpload class to test without internet, acts the same as the SpectromUpload class, but without going to the internet.
	Assists in testing UI features.
	"""
	def __init__(self, callback):
		super(FakeSpectromUpload, self).__init__()

	def isHostReachable(self):
		return True

	def createDesign(self, name, description, category, license):
		return 1

	def publishDesign(self, id):
		pass

	def createDocument(self, designId, name, contents):
		print "Create document: %s" % (name)
		f = open("C:/models/%s" % (name), "wb")
		f.write(contents)
		f.close()
		return 1

	def createImage(self, designId, name, contents):
		print "Create image: %s" % (name)
		f = open("C:/models/%s" % (name), "wb")
		f.write(contents)
		f.close()
		return 1

	def listDesigns(self):
		return []

	def _request(self, method, url, postData = None, files = None):
		print "Err: Tried to do request: %s %s" % (method, url)
