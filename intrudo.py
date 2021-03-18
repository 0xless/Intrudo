import asyncio
import itertools
import re
from functools import partial
from cliente import Cliente

#
# TODO refactor simple_list_generator
#
#

DELIMITERS = ("{{", "}}")
assert len(DELIMITERS) == 2, "DELIMITERS must be a pair of strings"


class Batch:
    def pitchfork(self, request, multiple_payload_list):
        """
            Given a list of tuple (of size #params), and a model of request,
            returns a list of requests with parameters injected.
            Each pair of DELIMITERS in the request model will be filled with the i-th value for that field.
        """

        # Check if tuples have the same length
        if not self._check_iterable_len(multiple_payload_list):
            raise Exception("Inconsistent payloads lengths")

        # Gets indexes of DELIMITERS
        positions = self._indexes(request, DELIMITERS)

        if len(positions) != len(multiple_payload_list):
            raise Exception("Number of DELIMITERS and number of parameters defined don't match")
        # if no DELIMITERS found and list empty return the request as batch
        elif len(positions) == 0:
            return [request]

        ret = []
        # Generates the requests
        for i in range(0, len(multiple_payload_list[0])):

            # convert to list to make the request editable
            dummy = list(request)
            # payload position index
            cont = 0
            # offset in positions because of the insertion of a payload
            offset = 0

            for x in positions:
                # get injection position (given position in the beginning and offset)
                start = x[0] + offset
                end = x[1] + offset

                # payload to use
                val = str(multiple_payload_list[cont][i])

                # update offset for the next injection
                len_old = end - start
                len_new = len(val)
                offset += len_new - len_old

                # injection
                dummy[start:end] = val
                cont += 1

            dummy = "".join(dummy)
            ret.append(dummy)
        return ret

    def sniper(self, request, single_payload_list):

        # Gets indexes of DELIMITERS
        positions = self._indexes(request, DELIMITERS)

        if len(positions) != len(single_payload_list):
            raise Exception("Number of DELIMITERS and number of parameters defined don't match")
        # if no DELIMITERS found and list empty return the request as batch
        elif len(positions) == 0:
            return [request]

        default_values = []
        # save default value for each field
        for x in positions:
            default_values.append(request[x[0]+len(DELIMITERS[0]):x[1]-len(DELIMITERS[1])])

        model = list(request)
        ret = []

        # for each payload
        for payload in single_payload_list:
            # inject the payload in each position
            for current in positions:
                # counter for default_values
                cont = 0
                dummy = model.copy()
                offset = 0

                # fill every injection position either with the default value or the payload value
                for pos in positions:
                    start = pos[0] + offset
                    end = pos[1] + offset

                    # if we found the position we want to inject the payload into
                    if pos == current:
                        dummy[start:end] = payload
                        # update offset for the next injection
                        len_old = end - start
                        len_new = len(payload)
                        offset += len_new - len_old
                    else:
                        dummy[start:end] = default_values[cont]
                        # update offset for the next injection
                        len_old = end - start
                        len_new = len(default_values[cont])
                        offset += len_new - len_old

                    cont += 1

                ret.append("".join(dummy))

        return ret

    def battering_ram(self, request, single_payload_list):
        # Gets indexes of DELIMITERS
        positions = self._indexes(request, DELIMITERS)

        model = list(request)
        ret = []

        # for each payload
        for payload in single_payload_list:
            offset = 0
            dummy = model.copy()

            # inject the payload in each position
            for pos in positions:
                start = pos[0] + offset
                end = pos[1] + offset

                dummy[start:end] = payload
                # update offset for the next injection
                len_old = end - start
                len_new = len(payload)
                offset += len_new - len_old

            ret.append("".join(dummy))

        return ret

    def cluster_bomb(self, request, multiple_payload_list):
        # Check if tuples have the same length
        if not self._check_iterable_len(multiple_payload_list):
            raise Exception("Inconsistent payloads lengths")

        # Gets indexes of DELIMITERS
        positions = self._indexes(request, DELIMITERS)

        if len(positions) != len(multiple_payload_list):
            raise Exception("Number of DELIMITERS and number of parameters defined don't match")
        # if no DELIMITERS found and list empty return the request as batch
        elif len(positions) == 0:
            return [request]

        ret = []
        # Generates the requests
        for i in itertools.product(*multiple_payload_list):
            ret.extend(self.pitchfork(request, list(map(lambda x:[x], i))))

        return ret

    # ----------------------------------------------------------------

    def _indexes(self, string, tuple_c):
        # escape special characters from delimiters
        delim_start, delim_end = self._escape_delimiters(tuple_c)

        # match anything between the delimiters (use greedy regex to handle multiple delimiters in one line)
        pattern = delim_start + ".*?" + delim_end

        # gets the indexes of first and last character of the matched string (excluding the delimiters)
        result = [(m.start(0), m.end(0)) for m in re.finditer(pattern, string)]

        return result

    def _escape_delimiters(self, tuple_c):
        # "\\" needs to be first or it might cause problems
        special = ["\\", ".", "^", "$", "*", "+", "?", "{", "[", "]", "|", "(", ")"]
        delim_start = tuple_c[0]
        delim_end = tuple_c[1]

        # escape any character in the delimiters considered special in regex
        for s in special:
            delim_start = delim_start.replace(s, '\\'+s)
            delim_end = delim_end.replace(s, '\\'+s)

        return delim_start, delim_end

    def _check_iterable_len(self, list_t):

        # check that length of every tuple is the same
        leng = 0
        for t in list_t:
            # is it's the first length observed
            if not leng:
                leng = len(t)
            else:
                if not leng == len(t):
                    return False
        return True


class Callback:
    def __init__(self, field, value, condition):
        self.field = field
        self.value = value
        self.condition = condition
        self.storage = {}
        self._id = 0

    def watch_value(self, request, response):
        self._watch_value(request, response, self.field, self.value)

    def watch_condition(self, request, response):
        self._watch_condition(request, response, self.condition)

    def _watch_value(self, request, response, field, value):
        if str(getattr(response, field, None)) == str(value):
            self.storage[self._id] = (request, response)
            self._id += 1

    def _watch_condition(self, request, response, condition_function):
        if condition_function(request, response):
            self.storage[self._id] = (request, response)
            self._id += 1


class Intrudo:
    class Response:
        def __init__(self, status, status_code, http_version, headers, body):
            self.status = status
            self.status_code = status_code
            self.http_version = http_version
            self.headers = headers
            self.body = body
            self.length = len(body)

    def __init__(self, url, callback = None):
        self.url = url
        self.loop = asyncio.get_event_loop()
        self.callback = callback

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

        if self.callback:
            self.callback(request, response)

        return response

    def fire(self, batch):
        self.loop.run_until_complete(self.manage_requests(batch))


def main():
    data = """
    GET /get?x={{param1}}&y={{param2}} HTTP/1.1
    Host: httpbin.org
    User-Agent: {{Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:86.0) Gecko/20100101 Firefox/86.0}}
    Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8
    Accept-Language: en-US,en;q=0.5
    Accept-Encoding: gzip, {{deflate}}, br
    Connection: keep-alive
    Upgrade-Insecure-Requests: 1
    DNT: 1
    Sec-GPC: 1
    Cache-Control: max-age=0"""

    url = "https://httpbin.org/"

    # batch = b.pitchfork(data, [[1,2,3,4,5,6,7,8,9,10], [12,22,32,42,52,62,72,82,92,102],
    #                    ["foo-"+str(x) for x in range(0,10)], ["bar-"+str(x) for x in range(20,30)]])
    # batch = b.sniper(data, ["1","2"])
    # batch = b.battering_ram(data, ["oof","rab"])
    b = Batch()
    batch = b.cluster_bomb(data, [["1","2"], ["foo","bar"], ["foofoo","barbar"], ["a", "b"]])

    # c = Callback("status_code", None, (lambda _, y: int(y.status_code) == 200))
    c = Callback("status_code", 200, None)
    intr = Intrudo(url, callback=c.watch_value)
    intr.fire(batch)

main()
