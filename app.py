import socket, _thread, sys, requests, os, time, datetime
from urllib.request import Request, urlopen, HTTPError
from cmd import Cmd

enc = 'utf-8'
bufferSize = 8192
cache = {}
blockedURLs = []

# Management Console.
class proxy_cmd(Cmd):

    prompt = "> "

    # Add URL to blocked list.
    def do_block(self, args):
        url = args.rsplit(" ", 1) 
        url = url[0]

        # Unify all saved URLs.
        if not "www." in url:
            url = "www." + url
        blockedURLs.append(url)
        print('Blocked:', url)
    
    # Show all the currently blocked URLs.
    def do_getblocked(self, args):
        print(blockedURLs)
    
    # Remove a previously blocked URL if it exists.
    def do_unblock(self, args):
        url = args.rsplit(" ", 1) 
        url = url[0]

        # Unify all saved URLs.
        if not "www." in url:
            url = "www." + url
        if url not in blockedURLs:
            print('This url had not been previously blocked.')
        else:
            blockedURLs.remove(url)
            print('Unblocked: ', url)
    
    # Display all available commands.
    def do_help(self, args):
        print("To block a URL type: `block` followed by the url.")
        print("To unblock a URL type: `unblock` followed by the url.")
        print("To see what URLS are currently blocked type: `getblocked`.")

# Web Proxy.
def startProxy():
    console = proxy_cmd()

    # Start thread that permanently listens to the console.
    conThread = _thread.start_new_thread(consoleThread, (console, None))

    # Start the server and make it listen on localhost port 8080.
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 8080))
        sock.listen(5)
        print("Server started successfully!")
    except Exception as e:
        print(e)
        sys.exit(2)
    
    print("Starting to listen for connections.")
    
    # Listens on port 8080 for connections.
    port = 8080
    while(1):
        try:
            conn, _ = sock.accept()
            req = conn.recv(bufferSize)

            # Starts new thread to deal with the request.
            _thread.start_new_thread(decodeRequest, (conn, req, port))
        except Exception as e:
            sock.close()
            print(e)
            sys.exit(1)

# Listens for user input.
def consoleThread(console, irr):
    console.cmdloop("Enter URL to be blocked: eg. block www.example.com or " +
        "help to see available commands.")

def decodeRequest(conn, req, port):
    try:
        # Breaks up the request into it's various components.
        check_method, url, baseURL, port = breakUpReq(req)

        # Necessary for checking a URL is blocked.
        if "www." not in baseURL:
            checkBlocked = "www." + baseURL
        else: 
            checkBlocked = baseURL
        
        # If the URL has been blocked, close the connection and inform the user that 
        # the site they're requesting is blocked.
        if checkBlocked in blockedURLs:
            print(f"{url} has been blocked.")
            conn.close()
            return
        else:
            # Re-encode the req into bytes.
            proxyServer(baseURL, url, port, conn, req, check_method)
    except Exception as e:
        pass

# Get the various information needed from the request.
def breakUpReq(req):
    # The recieved req is in bytes and therefore needs to be decoded.
    req = req.decode(enc)
    tmp = req.split('\n')[0]
    tmp = tmp.split(' ')

    # This is to tell whether we are dealing with HTTP or HTTPS.
    check_method = tmp[0]

    url = tmp[1]
    httpPos = url.find("://")

    # HTTP Request
    if check_method == "GET":
        tmp = url[(httpPos+3):]
    # HTTPS Request
    else:
        tmp = url[(httpPos+4):]
    
    portPos = tmp.find(":")
    baseURLPos = tmp.find("/")

    if baseURLPos == -1:
        baseURLPos = len(tmp)
    
    baseURL = ""
    port = -1

    # Default port.
    if portPos == -1 or baseURLPos < portPos:
        port = 80
        baseURL = tmp[:baseURLPos]
    
    # Specific port.
    else:
        port = int((tmp[(portPos+1):])[:baseURLPos-portPos-1])
        baseURL = tmp[:portPos]
        

    return check_method, url, baseURL, port 

def proxyServer(baseURL, url, port, conn, req, check_method):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Deals with HTTPS.
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

    # Deals with HTTP that has not been accessed before.
    else:
        if baseURL not in cache:
            tic = time.perf_counter()
            sock.connect((baseURL, port))
            sock.send(req)
            print(f"{url} has not previously been cached.")
            result = cacheRequest(url, baseURL)        
            
            if result:
                print("Caching as the page wanted has successfully been carried out.")
            else:
                print("Caching didn't work :(.")
            toc = time.perf_counter()
            
            print(f"Request took: {toc - tic:0.4f} seconds")

            try:
                while True:
                    resp = sock.recv(bufferSize)
                    if (len(resp) > 0):
                        conn.send(resp)
                        bandwidth = float(len(resp))/1024
                        bandwidth = "%.3s" % (str(bandwidth))
                        bandwidth = "%s KB" % (bandwidth)
                        print(f"Bandwidth Used: {bandwidth}")
                    else:
                        break
                sock.close()
                conn.close

            except socket.error:
                sock.close()
                conn.close()
                sys.exit(1)
            
        # Deals with HTTP that has been stored in cache previously and is not outdated.
        elif cache[baseURL] is not None and cache[baseURL] > datetime.datetime.now():
            print(f"{url} has previously been cached.")
            tic = time.perf_counter()
            info = getCachedVersion(baseURL)
            toc = time.perf_counter()
            print(f"Cache took: {toc - tic:0.4f} seconds")
            resp = 'HTTP/1.0 200 OK\n\n' + info
            conn.send(resp.encode())
        
        # The information cached is outdated and so therefore remove from cache.
        else:
            del cache[baseURL]
                
        sock.close()
        conn.close()

# Get info from cache.
def getCachedVersion(baseURL):
    try:
        readFile = open(baseURL)
        info = readFile.read()
        readFile.close()
        return info
    except IOError:
        return None

# Get info from server.
def cacheRequest(cacheFilename, baseURL):
    req = Request(cacheFilename)
    try:
        response = urlopen(req)
        responseHeaders = response.info()
        responseHeaders = responseHeaders.as_string().split("\n")
        expiry = None
        index = 0
        for header in responseHeaders:
            if 'cache-control' in header.lower():
                expiry = responseHeaders[index]
            index = index + 1
            
        # The page is not to be cached.
        if expiry is not None and "no-cache" in expiry.lower():
            return True

        # Determine when the cached result is no longer useful.
        if expiry is not None and "max-age" in expiry.lower():
            expiry = expiry.split('=')
            expiry = int(expiry[1])
            currTime = datetime.datetime.now()
            # Adds the amount of seconds to the current time.
            expiry = currTime + datetime.timedelta(0,expiry)
        
        # Adds the baseURL as the key to the cache dictionary along with the time its due to 
        # become invalid if  that exists.
        cache[baseURL] = expiry
        info = response.read().decode(enc)

        if info:
            print('Caching: ', cacheFilename)
            try:
                cachedFile = open(baseURL, 'w')
            except Exception as e:
                print(e)
            cachedFile.write(info)
            cachedFile.close()
            return True
        else:
            return False
    except HTTPError:
        return False

# Starts the proxy server.
startProxy()