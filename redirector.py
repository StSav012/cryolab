import time
import sys
from threading import Thread
import socket

class worker_redir(Thread):
    def __init__(self, port=5000):
        Thread.__init__(self)
        self.port = port
        self.daemon = True
    def run(self):
        print("HTTP 302 Redirector is active and listening on port", self.port)
        while True:
            try:        
#                print('connecting')
                connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#                print('waiting for connection')
    #            connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                connection.bind(('0.0.0.0', self.port))
                connection.listen(32)
#                print('bound to', self.port)
                current_connection, address = connection.accept()
#                print('accepted from', address)
                reply = '''\
HTTP/1.1 302 Encryption Required
Location: http://{TARGET}/
Connection: close
Cache-control: private

<html><body>Encryption Required.  Please go to <a href='http://{TARGET}/'>http://{TARGET}/</a> for this service.</body></html>
'''.format(TARGET = socket.gethostname())
                current_connection.send(reply.encode('ascii'))
                current_connection.close()
            except KeyboardInterrupt:
                connection.shutdown(1)
                connection.close()
                sys.exit()
            except:
    #            connection.shutdown(1)
                connection.close()
                pass
    #        except:
    #            pass
            finally:
                time.sleep(1)

