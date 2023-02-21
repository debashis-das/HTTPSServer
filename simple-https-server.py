"""Simple https server for development."""
from enum import Enum
import ssl
from urllib.error import URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse, urljoin
from http.server import HTTPServer, SimpleHTTPRequestHandler

CERTFILE = './server.pem'

PROXY_RULES = {
    '/ping': 'http://127.0.0.1:8080/ping',
}

FOLLOW_REDIRECT = True


class ReverseProxyStatus(Enum):
    SUCCESS = 1
    FAILED = 2
    REDIRECTED = 3


def main():
    https_server(certfile=CERTFILE)


class Handler(SimpleHTTPRequestHandler):

    def __do_proxy(self):
        prefix = None
        for key in PROXY_RULES:
            if self.path.startswith(key):
                prefix = key
                break

        if prefix:
            # Strip off the prefix.
            url = urljoin(PROXY_RULES[prefix], self.path.partition(prefix)[2])
            hostname = urlparse(PROXY_RULES[prefix]).netloc

            body = None
            if self.headers['content-length'] is not None:
                content_len = int(self.headers['content-length'])
                body = self.rfile.read(content_len)

            # set new headers
            new_headers = {}
            for item in self.headers:
                new_headers[item[0]] = item[1]
            new_headers['host'] = hostname
            try:
                del new_headers['accept-encoding']
            except KeyError:
                pass
            response = self.__do_request(url, body, new_headers)
            if response[0] == ReverseProxyStatus.SUCCESS:
                self.send_response(200)
                self.end_headers()
                self.copyfile(response[1], self.wfile)
            else:
                print("Inner call failed/redirected")
        else:
            print(f"{prefix if prefix else '/'} unregistered")

    def __do_request(self, url, body, headers):
        req = Request(url, body, headers)
        try:
            response = urlopen(req)
            return ReverseProxyStatus.SUCCESS, response
        except URLError as e:
            if FOLLOW_REDIRECT and hasattr(e, 'code') and (e.code == 301 or e.code == 302):
                headers['host'] = urlparse(e.url).netloc
                return ReverseProxyStatus.REDIRECTED, self.__do_request(e.url, body, headers)
            else:
                response = e
        return ReverseProxyStatus.FAILED, response

    def do_GET(self):
        self.__do_proxy()


def https_server(*, certfile):
    print('`https_server()` starts...')
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(CERTFILE)

    server_address = ('', 443)
    with HTTPServer(server_address, Handler) as httpd:
        httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
        print_server_info(httpd)
        try:
            httpd.serve_forever()
        except Exception as e:
            httpd.server_close()
            raise e


def print_server_info(server):
    print(f"""Server info:
    name: {server.server_name}
    address: {server.server_address}
    """)


if __name__ == "__main__":
    main()
