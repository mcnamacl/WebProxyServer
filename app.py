import socket, _thread, sys, requests, os, time
from urllib.request import Request, urlopen, HTTPError
from cmd import Cmd
import datetime

max_conn = 5
bufferSize = 8192
cache = {}
blockedURLs = []

class proxy_cmd(Cmd):

    prompt = "> "

    def do_block(self, args):
        url = args.rsplit(" ", 1) 
        url = url[0]
        if not "www." in url:
            url = "www." + url
        blockedURLs.append(url)
        print('Blocked :', url)
    
    def do_getblocked(self, args):
        print(blockedURLs)
    
    def do_unblock(self, args):
        url = args.rsplit(" ", 1) 
        url = url[0]
        if not "www." in url:
            url = "www." + url
        if url not in blockedURLs:
            print('This url had not been previously blocked.')
        else:
            blockedURLs.remove(url)
            print('Unblocked : ', url)
    
    def do_help(self, args):
        print("To block a URL type: `block` followed by the url.")
        print("To unblock a URL type: `unblock` followed by the url.")
        print("To see what URLS are currently blocked type: `getblocked`.")

def startProxy():
    console = proxy_cmd()
    conThread = _thread.start_new_thread(consoleThread, (console, None))
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
        tmp = data.split('\n')[0]
        tmp = tmp.split(' ')

        # This is to tell whether we are dealing with HTTP or HTTPS.
        check_method = tmp[0]

        url = tmp[1]
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

        if "www." not in baseURL:
            checkBlocked = "www." + baseURL
        else: 
            checkBlocked = baseURL
        if checkBlocked in blockedURLs:
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
                # print("Request Complete: %s Bandwidth Used: %s " % (str(baseURL), str(bandwidth)))
            except socket.error as e:
                pass

    # HTTP that has not been accessed before.
    else:
        if baseURL not in cache:
            tic = time.perf_counter()
            sock.connect((baseURL, port))
            sock.send(data)
            print("This request has not previously been cached.")
            serv_file = getFromServer(url, baseURL)
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
        elif cache[baseURL] is not None and cache[baseURL] > datetime.datetime.now():
            tic = time.perf_counter()
            content = getFromCache(baseURL)
            toc = time.perf_counter()
            print(f"Cache took: {toc - tic:0.4f} seconds")
            resp = 'HTTP/1.0 200 OK\n\n' + content
            conn.send(resp.encode())
        
        # Remove from cache.
        else:
            del cache[baseURL]
                
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

def getFromServer(filename, baseURL):
    req = Request(filename)
    try:
        response = urlopen(req)
        response_headers = response.info()
        response_headers = response_headers.as_string().split("\n")
        expiry = None
        index = 0
        for header in response_headers:
            if 'cache-control' in header.lower():
                expiry = response_headers[index]
            index = index + 1
            
        # The page is not to be cached.
        if expiry is not None and "no-cache" in expiry.lower():
            return

        # Determine when the cached result is no longer useful.
        if expiry is not None and "max-age" in expiry.lower():
            expiry = expiry.split('=')
            expiry = int(expiry[1])
            currTime = datetime.datetime.now()
            expiry = currTime + datetime.timedelta(0,expiry)
        cache[baseURL] = expiry
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