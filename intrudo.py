import asyncio
from cliente import Cliente

SYMBOL = "⛶"

class Batch():
	def simple_list_generator(request, list_t):
		"""
		Given a list of tuple (of size #params), and a model of request,
		returns a list of requests filled with the params.
		Each SYMBOL in the request model will be filled with the i-th value for that field.
		"""
		leng = 0

		# Check if tuples have the same length
		for t in list_t:
			if not leng:
				leng = len(t)
			else:
				if not leng == len(t):
					raise Exception("Inconsistent tuple lengths") 

		# Gets indexes of SYMBOL
		positions = Batch._indexes(request, SYMBOL)

		if len(positions) != len(list_t):
			raise Exception("Number of symbols and number of parameters defined don't match") 
		# if no symbols found and list empty return the request as batch
		elif len(positions) == 0:
			return [request]

		ret = []
		# Generates the requests
		for i in range(0, leng):
			dummy = list(request)

			for x in range(0, len(positions)):
				dummy[positions[x]] = str(list_t[x][i])

			dummy = "".join(dummy)
			ret.append(dummy)

		return ret

	def _indexes(string, char):
		return [i for i, letter in enumerate(string) if letter == char]

class Intrudo:
	class Response:
		def __init__(self, status, status_code, http_version, headers, body):
			self.status = status
			self.status_code = status_code
			self.http_version = http_version
			self.headers = headers
			self.body = body

	def __init__(self, url):
		self.url = url
		self.loop = asyncio.get_event_loop()

	async def _setup(self, client):
		await client.connect()

	async def manage_requests(self, request_batch):
		tasks = [asyncio.ensure_future(self.make_request(r)) for r in request_batch]
		return await asyncio.gather(*tasks)

	async def make_request(self, request, format_data=True):
		client = Cliente(self.url)
		await self._setup(client)

		if format_data:
			request = client.format(request)

		client.send(request)
		await client.receive()

		response = Intrudo.Response(client.status, client.status_code, client.http_version, client.headers, client.body)

		# Callback here!!!!
		# Demo purposes only
		print(response.body)

		return response

	def fire(self, batch):
		self.loop.run_until_complete(self.manage_requests(batch))

def main():
	data = """
			GET /get?x=⛶&y=⛶ HTTP/1.1
			Host: httpbin.org
			User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:86.0) Gecko/20100101 Firefox/86.0
			Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8
			Accept-Language: en-US,en;q=0.5
			Accept-Encoding: gzip, deflate, br
			Connection: keep-alive
			Upgrade-Insecure-Requests: 1
			DNT: 1
			Sec-GPC: 1
			Cache-Control: max-age=0"""

	url = "https://httpbin.org/"
			
	batch = Batch.simple_list_generator(data, [(1,2,3), ("a","b","c")])
	
	intr = Intrudo(url)
	intr.fire(batch)

main()

	

