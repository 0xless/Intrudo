import asyncio
import urllib.parse
import textwrap

from decoder import Decoder as decoder

#
# TODO: test _bytes_to_string
# TODO: check if _bytes_to_string to_decode list is correct
# TODO: restructure self.http_version, self.status_code, self.status (not to be class variables)
#

class Cliente(): 
	def __init__(self, url, ssl=True):
		# If url scheme is http, ssl parameter is ignored
		url = urllib.parse.urlsplit(url)
		self.scheme = url.scheme
		self.hostname = url.hostname
		self.ssl = ssl

		self.reader = None
		self.writer = None

	async def connect(self):
		""" Connects to the host specified in the URL """
		if self.scheme == 'https':
			reader, writer = await asyncio.open_connection(
				self.hostname, 443, ssl=self.ssl)
		else:
			reader, writer = await asyncio.open_connection(
				self.hostname, 80)

		self.reader = reader
		self.writer = writer

	def format(self, payload):
		""" Formats the request removing common copy-paste induced incompatibilities """
		# Steps:
		# - strips any common leading whitespace from every line in text
		# - adds \r\n\r\n at the end of the request (this shouldn't cause problems)

		return textwrap.dedent(payload) + "\r\n\r\n"

	def send(self, data):
		""" Sends the request """
		assert self.writer and self.reader, "no connection exists, make sure to call the connect() function before send()"
		self.writer.write(data.encode('utf-8'))

	def _bytes_to_string(self, data, headers):
		# list of data to try to decode
		to_decode = ["application", "text", "message"]	

		tmp_type = headers.get("content-type")
		if tmp_type:
			if "charset=" in tmp_type:

				for td in to_decode:
					if td in tmp_type:
						tmp = tmp_type.split("=")[1]
						try:
							return data.decode(tmp)
						except UnicodeDecodeError:
							# fallback encoding
							return data.decode("latin-1")
			else:
				to_decode = ["application", "text", "message"]	

				for td in to_decode:
					if td in tmp_type:
						#fallback encoding
						return data.decode("latin-1")
		return data

	async def receive(self):
		""" Reads data from the socket and handle headers and body retrieval """
		headers = {}
		is_first_line = True

		# valid response flag
		valid = True

		# Handle headers retrieval
		while True:
			line = await self.reader.readline()
			if line == b"\r\n":
				break
			else:
				if(is_first_line):
					# Manages first line of response
					# HTTP/{version} {status_code} {status}
					
					# Only 2 splits because some statuses will contain spaces (like "Bad Request")
					first_line = line.decode('latin1').split(" ", 2)
					if len(first_line) == 3:
						(self.http_version, self.status_code, self.status) = first_line
					# if first line is invalid break
					else:
						(self.http_version, self.status_code, self.status) = None, None, None
						valid = False
						break

					is_first_line = False
				else:
					# Extracts headers from the response
					# header: value

					# Only 1 split because some headers (like date) will contain the ":" char
					line = line.decode('latin1').split(":", 1)
					if len(line) == 2:
						(key, val) = line
						key = key.strip(" \r\n").lower()
						val = val.strip(" \r\n")
						headers[key] = val

		# Handle body retrieval
		if valid:
			length = headers.get("content-length")
		else:
			length = 0

		# Content length specified
		if length is not None:
			body = await self.reader.readexactly(int(length))

			d = decoder(headers)
			body = self._bytes_to_string(d.decode(body), headers)

		# Chunked transfer encoding
		else:
			d = decoder(headers)
			first = True

			while True:
				hex_len = self._bytes_to_string(d.decode(await self.reader.readline()), headers)
				length = int(hex_len, 16)
				
				if(length != 0):
					line = self._bytes_to_string(d.decode(await self.reader.readexactly(length)), headers)

					if first:
						body = line
						first = False
					else:
						body += line

					# ignore empty line
					_ = await self.reader.readline()
				else:
					#TODO manage headers sent after chunks
					break  

		self.headers = headers
		self.body = body

		self.writer.close()