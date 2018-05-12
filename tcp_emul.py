import time
import sys
from threading import Thread
import socket

class worker(Thread):
    def __init__(self, temperature_controller=None, port=1394):
        Thread.__init__(self)
        self.port = port
        self.tmpr = temperature_controller
        self.daemon = True
    def run(self):
#        print('tcp running')
        while True:
            try:        
#                print('connecting')
                connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#                print('waiting for connection')
    #            connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                connection.bind(('0.0.0.0', self.port))
                connection.listen(32)
#                print('bound to', self.port)
                while True:
                    current_connection, address = connection.accept()
#                    print('accepted from', address)
                    while True:
                        data = current_connection.recv(256).decode('ascii').lower()
                        print(time.time(), 'received', data)
                        for cmd in data.split(';'):
#                            print('command:', cmd)
                            reply = '-1'
                            cmd = cmd.strip(' :')
                            if self.tmpr and cmd.startswith('krdg? a'):
                                reply = repr(self.tmpr.temperatures[0])
                            elif self.tmpr and cmd.startswith('krdg? b'):
                                reply = repr(self.tmpr.temperatures[1])
                            print(time.time(), 'sending', reply)
                            current_connection.send((reply + '\n').encode('ascii'))
                            print(time.time(), 'done')
            except (KeyboardInterrupt, SystemExit):
                connection.shutdown(1)
                connection.close()
                print('caught ctrl+c')
                self.join()
                sys.exit()
            except:
    #            connection.shutdown(1)
                connection.close()
                pass
    #        except:
    #            pass
            finally:
                time.sleep(1)

