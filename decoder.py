import zlib
try:
	try:
		import brotlicffi as brotli
	except ImportError:
		import brotli
except ImportError:
	brotli = None

class ContentDecoder:
	def decompress(self, data: bytes) -> bytes:
		raise NotImplementedError()

	def flush(self) -> bytes:
		raise NotImplementedError()


class DeflateDecoder(ContentDecoder):
	def __init__(self):
		self._first_try = True
		self._data = b""
		self._obj = zlib.decompressobj()

	def decompress(self, data):
		if not data:
			return data

		if not self._first_try:
			return self._obj.decompress(data)

		self._data += data
		try:
			decompressed = self._obj.decompress(data)
			if decompressed:
				self._first_try = False
				self._data = None
			return decompressed
		except zlib.error:
			self._first_try = False
			self._obj = zlib.decompressobj(-zlib.MAX_WBITS)
			try:
				return self.decompress(self._data)
			finally:
				self._data = None

	def flush(self) -> bytes:
		return self._obj.flush()


class GzipDecoderState:

	FIRST_MEMBER = 0
	OTHER_MEMBERS = 1
	SWALLOW_DATA = 2


class GzipDecoder(ContentDecoder):
	def __init__(self):
		self._obj = zlib.decompressobj(16 + zlib.MAX_WBITS)
		self._state = GzipDecoderState.FIRST_MEMBER

	def decompress(self, data):
		ret = bytearray()
		if self._state == GzipDecoderState.SWALLOW_DATA or not data:
			return bytes(ret)
		while True:
			try:
				ret += self._obj.decompress(data)
			except zlib.error:
				previous_state = self._state
				# Ignore data after the first error
				self._state = GzipDecoderState.SWALLOW_DATA
				if previous_state == GzipDecoderState.OTHER_MEMBERS:
					# Allow trailing garbage acceptable in other gzip clients
					return bytes(ret)
				raise
			data = self._obj.unused_data
			if not data:
				return bytes(ret)
			self._state = GzipDecoderState.OTHER_MEMBERS
			self._obj = zlib.decompressobj(16 + zlib.MAX_WBITS)

	def flush(self) -> bytes:
		return self._obj.flush()


if brotli is not None:

	class BrotliDecoder(ContentDecoder):
		# Supports both 'brotlipy' and 'Brotli' packages
		# since they share an import name. The top branches
		# are for 'brotlipy' and bottom branches for 'Brotli'
		def __init__(self):
			self._obj = brotli.Decompressor()
			if hasattr(self._obj, "decompress"):
				self.decompress = self._obj.decompress
			else:
				self.decompress = self._obj.process

		def flush(self):
			if hasattr(self._obj, "flush"):
				return self._obj.flush()
			return b""


class MultiDecoder(ContentDecoder):
	"""
	From RFC7231:
		If one or more encodings have been applied to a representation, the
		sender that applied the encodings MUST generate a Content-Encoding
		header field that lists the content codings in the order in which
		they were applied.
	"""

	def __init__(self, modes):
		self._decoders = [_get_decoder(m.strip()) for m in modes.split(",")]

	def flush(self):
		return self._decoders[0].flush()

	def decompress(self, data):
		for d in reversed(self._decoders):
			data = d.decompress(data)
		return data


def _get_decoder(mode):
	if "," in mode:
		return MultiDecoder(mode)

	if mode == "gzip":
		return GzipDecoder()

	if brotli is not None and mode == "br":
		return BrotliDecoder()

	return DeflateDecoder()


class Decoder():
	CONTENT_DECODERS = ["gzip", "deflate"]
	if brotli is not None:
		CONTENT_DECODERS += ["br"]
	REDIRECT_STATUSES = [301, 302, 303, 307, 308]

	DECODER_ERROR_CLASSES = (IOError, zlib.error)
	if brotli is not None:
		DECODER_ERROR_CLASSES += (brotli.error,)


	def __init__(self, headers):
		self._decoder = None
		self.headers = headers

	def decode(self, data, flush_decoder = False):
		"""
		Decode the data passed in and potentially flush the decoder.
		"""
		self._init_decoder()

		try:
			if self._decoder:
				data = self._decoder.decompress(data)
		except self.DECODER_ERROR_CLASSES as e:
			content_encoding = self.headers.get("content-encoding", "").lower()
			raise DecodeError(
				"Received response with content-encoding: %s, but "
				"failed to decode it." % content_encoding,
				e,
			)

		if flush_decoder:
			data += self._flush_decoder()

		return data

	def _init_decoder(self):
		"""
		Set-up the _decoder attribute if necessary.
		"""
		# Note: content-encoding value should be case-insensitive, per RFC 7230
		# Section 3.2
		content_encoding = self.headers.get("content-encoding", "").lower()

		if self._decoder is None:
			if content_encoding in self.CONTENT_DECODERS:
				self._decoder = _get_decoder(content_encoding)
			elif "," in content_encoding:
				encodings = [
					e.strip()
					for e in content_encoding.split(",")
					if e.strip() in self.CONTENT_DECODERS
				]
				if len(encodings):
					self._decoder = _get_decoder(content_encoding)

	def _flush_decoder(self):
		"""
		Flushes the decoder. Should only be called if the decoder is actually
		being used.
		"""
		if self._decoder:
			return self._decoder.decompress(b"") + self._decoder.flush()
		return b""