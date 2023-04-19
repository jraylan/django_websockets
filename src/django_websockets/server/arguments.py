
import argparse
import re


IPV6_REGEX = r'(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))'
IPV4_REGEX = r'(\b25[0-5]|\b2[0-4][0-9]|\b[01]?[0-9][0-9]?)(\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3}'
HOSTNAME_REGEX = r'[-a-zA-Z0-9%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b'
IP_ADDRESS_REGEX = '((\['+IPV6_REGEX+'\]|'+IPV4_REGEX +'|'+HOSTNAME_REGEX+'|localhost):(\d+))'
PORT_REGEX = r'((6553[0-5])|(655[0-2][0-9])|(65[0-4][0-9]{2})|(6[0-4][0-9]{3})|([1-5][0-9]{4})|([0-5]{0,5})|([0-9]{1,4}))'
UNIX_REGEX = r'unix:(\/[\w-]+)+(.[a-zA-Z]+?)$'


class WebsocketBindAddress(object):

    def __init__(self, address, port=None, is_unix=False):
        self.__address = address
        self.__port = port
        self.__is_unix = is_unix

    @property
    def address(self):
        return self.__address

    @property
    def port(self):
        return self.__port

    @property
    def is_unix(self):
        return self.__is_unix
    
    def get_namespaced_address(self, namespace):
        address = self.address
        if namespace and self.is_unix and namespace != "master":
            if address.endswith('.socket'):
                address = address[:-6]
                address = f'{address}{namespace}.socket'
            elif address.endswith('.sock'):
                address = address[:-4]
                address = f'{address}{namespace}.sock'
            else:
                address = f'{address}{namespace}.socket'

        return address


    def __str__(self):
        if self.port:
            return f'{self.address}:{self.port}'
        return f'{self.address}'

    def __repr__(self) -> str:
        return f'<WebsocketBindAddress address={self.address} port={self.port} is_unix={self.is_unix}>'

    def validate(self):
        pass


class BindType(object):

    error_messages = {
        'ipv4_not_allowed': 'Endereços IPv4 não é permitido.',
        'ipv6_not_allowed': 'Endereços IPv6 não é permitido.',
        'unix_not_allowed': 'Endereços unix não é permitido.',
        'invalid_address': 'O argumento "%(argument)s" é inválido.',
        'invalid_unix_address': 'O argumento "%(argument)s" não é um endereço unix válido.',
        'invalid_port': 'O argumento "%(port)s" não é uma porta válida.',
    }

    def __init__(self, ipv4=True, ipv6=True, unix=True):
        self.ipv4 = ipv4
        self.ipv6 = ipv6
        self.unix = unix
        if not ipv4 and not ipv6 and not unix:
            raise RuntimeError("At least one address type must be accepted")


    def __call__(self, string:str):
        self.__address = string

        unix = string.startswith('unix:')
        addr = None
        port = None
        if unix:
            if self.unix:
                if not re.match(UNIX_REGEX, string):
                    raise argparse.ArgumentTypeError(
                        self.error_messages['invalid_unix_address'] % {
                            'argument': string,
                        })

                port = None
                addr = string[5:]
            else:
                raise argparse.ArgumentTypeError(self.error_messages['unix_not_allowed'])
        else:
            ip_regex = re.compile(IP_ADDRESS_REGEX)
            ipv4_regex = re.compile('(('+IPV4_REGEX+'):(\d+))')
            ipv6_regex = re.compile('(('+IPV6_REGEX+'):(\d+))')
            port_regex = re.compile(PORT_REGEX)

            if self.ipv4 and self.ipv4:
                regex = ip_regex
            elif self.ipv4:
                if ipv6_regex.match(string):
                    raise argparse.ArgumentTypeError(
                        self.error_messages['ipv6_not_allowed'] % {
                            'argument': string
                        }
                    )
                regex = ipv4_regex
            elif self.ipv6:
                if ipv4_regex.match(string):
                    raise argparse.ArgumentTypeError(
                        self.error_messages['ipv4_not_allowed'] % {
                            'argument': string
                        }
                    )
                regex = ipv6_regex
            else:
                raise argparse.ArgumentTypeError(
                    self.error_messages['invalid_unix_address'] % {
                        'argument': string
                    })

            r_match = regex.match(string)
            if not r_match:
                raise argparse.ArgumentTypeError(self.error_messages['invalid_address'] % {
                    'argument': string
                })
            
            r_groups = r_match.groups()
            addr, port = (
                r_groups[1],
                r_groups[-1]
            )

            if not port_regex.match(port):
                raise argparse.ArgumentTypeError(self.error_messages['invalid_port'] % {
                    'port': port
                })
            
            port = int(port)
            
        return WebsocketBindAddress(
            addr, port, is_unix=unix
        )

    def __repr__(self):
        return '%s(%s)' % (type(self).__name__, self.__address)
    

class RegexType(object):
    error_messages = {
        'invalid': 'O argumento "%(argument)s" é inválido.',
    }
    def __init__(self, regex:str):
        self.__regex = re.compile(regex)

    def __call__(self, string: str):
        if self.__regex.match(string):
            return string
        
        raise argparse.ArgumentTypeError(
            self.error_messages['invalid'] % {
                'argument': string
            }
        )


def workers(val):
    val = int(val)
    if val <1:
        raise argparse.ArgumentTypeError(
            "%s is an invalid positive int value" % val)
    return val


parser = argparse.ArgumentParser(
    prog='Websocket',
    description='A websocket server')

parser.add_argument('-b', '--bind', nargs=1, required=True, type=BindType())
parser.add_argument('-s', '--settings', nargs=1, required=True,
                    type=RegexType(r'([a-zA-Z0-9_](\.[a-zA-Z0-9_]){0,})'))
parser.add_argument('-w', '--workers', nargs=1, required=True, type=workers)

