import socket, _thread, sys, requests, os, time
from urllib.request import Request, urlopen, HTTPError
from cmd import Cmd

max_conn = 5
bufferSize = 8192
cache = []
blockedURLs = []

class proxy_cmd(Cmd):

    prompt = "> "

    def do_block(self, args):
        url = args.rsplit(" ", 1) # args is string of input after create
        url = url[0]
        blockedURLs.append(url)
        print('Blocked :', url)
    
    def do_getblocked(self, args):
        print(blockedURLs)
    
    def do_help(self, args):
        print("To block a URL type: `block` followed by the url.")
        print("To see what URLS are currently blocked type: `getblocked`.")
        print("To exit type: `exit`.")

    def do_exit(self, args):
        raise SystemExit()

def startProxy():
    console = proxy_cmd()
    _thread.start_new_thread(consoleThread, (console, None))
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 8080))
        sock.listen(max_conn)
        print("Server started successfully!")
    except Exception as e:
        print(e)
        sys.exit(2)
    
    print("Starting to listen for connections...")
    # Listens on port 8080 for connections.
    port = 8080
    while(1):
        try:
            conn, _ = sock.accept()
            data = conn.recv(bufferSize)
            _thread.start_new_thread(decodeRequest, (conn, data, port))
        except Exception as e:
            sock.close()
            print(e)
            sys.exit(1)

def consoleThread(console, irr):
    console.cmdloop("Enter URL to be blocked: eg. block www.example.com or help to see available commands.")

def decodeRequest(conn, data, port):
    try:
        encoding = 'utf-8'

        # The recieved data is in bytes and therefore needs to be decoded.
        data = data.decode(encoding)
        first_line = data.split('\n')[0]
        first_line = first_line.split(' ')

        # This is to tell whether we are dealing with HTTP or HTTPS.
        check_method = first_line[0]

        url = first_line[1]
        http_pos = url.find("://")
        if (http_pos == -1):
            tmp = url
        # HTTP Request
        elif check_method == "GET":
            tmp = url[(http_pos+3):]
        # HTTPS Request
        else:
            tmp = url[(http_pos+4):]
        
        port_pos = tmp.find(":")

        baseURL_pos = tmp.find("/")

        if baseURL_pos == -1:
            baseURL_pos = len(tmp)
        
        baseURL = ""

        port = -1

        # Default port.
        if port_pos == -1 or baseURL_pos < port_pos:
            port = 80
            baseURL = tmp[:baseURL_pos]
        
        # Specific port.
        else:
            port = int((tmp[(port_pos+1):])[:baseURL_pos-port_pos-1])
            baseURL = tmp[:port_pos]

        if baseURL in blockedURLs:
            print(f"{url} has been blocked.")
            conn.close()
            return
        else:
            # Re-encode the data into bytes.
            data = data.encode(encoding)
            proxyServer(baseURL, url, port, conn, data, check_method)
    except Exception as e:
        pass

def proxyServer(baseURL, url, port, conn, data, check_method):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # HTTPS 
    if check_method == "CONNECT":
        try:
            sock.connect((baseURL, port))
            resp = "HTTP/1.0 200 Connection established\r\nProxy-agent: Claires_Proxy\r\n\r\n"
            conn.sendall(resp.encode())
            print(f"Connecting to: {baseURL}.")
        except socket.error as e:
            print(e)
            return

        conn.setblocking(0)
        sock.setblocking(0)

        while True:
            try:
                request = conn.recv(bufferSize)
                sock.sendall(request)
            except socket.error as e:
                pass
            try:
                resp = sock.recv(bufferSize)
                conn.sendall(resp)
                bandwidth = float(len(resp))
                bandwidth = float(bandwidth/1024)
                bandwidth = "%.3s" % (str(bandwidth))
                bandwidth = "%s KB" % (bandwidth)
                #print("Request Complete: %s Bandwidth Used: %s " % (str(baseURL), str(bandwidth)))
            except socket.error as e:
                pass

    # HTTP that has not been accessed before.
    else:
        if baseURL not in cache:
            tic = time.perf_counter()
            sock.connect((baseURL, port))
            sock.send(data)
            cache.append(baseURL)
            print("This request has not previously been cached.")
            serv_file = getFromServer(url)
            if serv_file:
                saveInCache(url, baseURL, serv_file)
            
            toc = time.perf_counter()
            print(f"Request took: {toc - tic:0.4f} seconds")

            try:
                while True:
                    resp = sock.recv(bufferSize)
                    if (len(resp) > 0):
                        conn.send(resp)
                        bandwidth = float(len(resp))
                        bandwidth = float(bandwidth/1024)
                        bandwidth = "%.3s" % (str(bandwidth))
                        bandwidth = "%s KB" % (bandwidth)
                        print("Request Complete: %s Bandwidth Used: %s " % (str(baseURL), str(bandwidth)))
                    else:
                        break
                sock.close()
                conn.close

            except socket.error:
                sock.close()
                conn.close()
                sys.exit(1)
            
        # HTTP that has been stored in cache previously.
        else:
            tic = time.perf_counter()
            content = getFromCache(baseURL)
            toc = time.perf_counter()
            print(f"Cache took: {toc - tic:0.4f} seconds")
            resp = 'HTTP/1.0 200 OK\n\n' + content
            conn.send(resp.encode())
                
        sock.close()
        conn.close()

def getFromCache(baseURL):
    try:
        fin = open(baseURL)
        content = fin.read()
        fin.close()
        return content
    except IOError:
        return None


def getFromServer(filename):
    req = Request(filename)
    try:
        response = urlopen(req)
        response_headers = response.info()
        content = response.read().decode('utf-8')
        return content
    except HTTPError:
        return None


def saveInCache(filename, baseURL, content):
    print('Saving a copy of {} in the cache'.format(filename))
    try:
        cached_file = open(baseURL, 'w')
    except Exception as e:
        print(e)
    cached_file.write(content)
    cached_file.close()


startProxy()