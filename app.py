import socket, _thread, sys, requests, os, time, datetime
from urllib.request import Request, urlopen, HTTPError
from cmd import Cmd

enc = 'utf-8'
bufferSize = 8192
cache = {}
blockedURLs = []
blockedURLHist = []

# Management Console.
class proxy_cmd(Cmd):

    prompt = "> "

    # Add URL to blocked list.
    def do_block(self, args):
        try:
            url = args.rsplit(" ", 1) 
            url = url[0]
        except Exception as e:
            print("Please enter a url.")

        # Unify all saved URLs.
        if not "www." in url:
            url = "www." + url
        blockedURLs.append(url)
        if url not in blockedURLHist and len(blockedURLHist) <= 10:
            blockedURLHist.append(url)
        print('Blocked:', url)
    
    # Show all the currently blocked URLs.
    def do_getblocked(self, args):
        if len(blockedURLs) == 0:
            print("No URLs are currently blocked however here are some " +
            "previously blocked URLs: ", blockedURLHist)
        else:
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
    
    def do_unblockall(self, args):
        del blockedURLs[:]
        print("All URLs have been unblocked.")
    
    # Display all available commands.
    def do_help(self, args):
        print("> To block a URL type: `block` followed by the url.")
        print("> To unblock a URL type: `unblock` followed by the url.")
        print("> To unblock all blocked urls type: `unblockall`.")
        print("> To see what URLS are currently blocked type: `getblocked`.")

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
    
    log("Server started successfully!")
    log("Starting to listen for connections.")
    print("Starting to listen for connections.")
    
    # Listens on port 8080 for connections.
    port = 8080
    while(1):
        try:
            cliConn, _ = sock.accept()
            req = cliConn.recv(bufferSize)

            # Starts new thread to deal with the request.
            _thread.start_new_thread(decodeRequest, (cliConn, req, port))
        except Exception as e:
            sock.close()
            print(e)
            sys.exit(1)

# Listens for user input.
def consoleThread(console, irr):
    console.cmdloop("Enter URL to be blocked: eg. block www.example.com or " +
        "help to see available commands.")

def decodeRequest(cliConn, req, port):
    try:
        # Breaks up the request into it's various components.
        checkMethod, url, baseURL, port = breakUpReq(req)

        # print("Connecting to: ", baseURL)
        log("Connecting to: " + baseURL)

        # Necessary for checking a URL is blocked.
        if "www." not in baseURL:
            checkBlocked = "www." + baseURL
        else: 
            checkBlocked = baseURL
        
        # If the URL has been blocked, close the connection and inform the user that 
        # the site they're requesting is blocked.
        if checkBlocked in blockedURLs:
            print(f"{url} has been blocked.")
            log(f"Tried to access the blocked URL: {url}")
            # Cutting off the connection.
            cliConn.close()
            return
        else:
            # Re-encode the req into bytes.
            proxyServer(baseURL, url, port, cliConn, req, checkMethod)
    except Exception as e:
        pass

# Get the various information needed from the request.
def breakUpReq(req):
    # The recieved req is in bytes and therefore needs to be decoded.
    req = req.decode(enc)
    tmp = req.split('\n')[0]
    tmp = tmp.split(' ')

    # This is to tell whether we are dealing with HTTP or HTTPS.
    checkMethod = tmp[0]

    url = tmp[1]
    httpPos = url.find("://")

    if (httpPos == -1):
        tmp = url
    # HTTP Request
    elif checkMethod == "GET":
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
        

    return checkMethod, url, baseURL, port 

def proxyServer(baseURL, url, port, cliConn, req, checkMethod):    

    newSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Deals with HTTPS aka CONNECT requests.
    if checkMethod == "CONNECT":
        try:
            newSock.connect((baseURL, port))
            resp = "HTTP/1.0 200 Connection established\r\nProxy-agent: Claires_Proxy\r\n\r\n"
            cliConn.sendall(resp.encode())
            # print(f"Connecting to: {baseURL}.")
        except socket.error as e:
            print(e)
            return

        cliConn.setblocking(0)
        newSock.setblocking(0)  

        while True:
            try:
                request = cliConn.recv(bufferSize)
                newSock.sendall(request)
            except socket.error as e:
                pass
            try:
                resp = newSock.recv(bufferSize)
                cliConn.sendall(resp)
                if len(resp) > 0:
                    bandwidth = float(len(resp))
                    bandwidth = float(bandwidth/1024)
                    bandwidth = "%.3s" % (str(bandwidth))
                    bandwidth = "%s KB" % (bandwidth)
                    # log("Request Complete: %s Bandwidth Used: %s " % (str(baseURL), str(bandwidth)))
                    # print("Request Complete: %s Bandwidth Used: %s " % (str(baseURL), str(bandwidth)))
            except socket.error as e:
                pass

    # Deals with HTTP aka GET requests.
    else:
        # Deals with HTTP that has not been accessed before.
        if baseURL not in cache:
            tic = time.perf_counter()
            newSock.connect((baseURL, port))
            newSock.send(req)
            # print(f"{url} has not previously been cached.")
            log(str(url) + " had not previously been cached.")
            result = cacheRequest(url, baseURL)        
            
            if result:
                # print("Caching as the page wanted has successfully been carried out.")
                log("Caching as the page wanted has successfully been carried out.")
            else:
                # print("Caching didn't work :(.")
                log("Caching didn't work :(.")
            toc = time.perf_counter()
            
            print(f"Request for {baseURL} took: {toc - tic:0.4f} seconds")
            log(f"Request for {baseURL} took: {toc - tic:0.4f} seconds")

            try:
                while True:
                    resp = newSock.recv(bufferSize)
                    if (len(resp) > 0):
                        cliConn.send(resp)
                        bandwidth = float(len(resp))/1024
                        bandwidth = "%.3s" % (str(bandwidth))
                        bandwidth = "%s KB" % (bandwidth)
                        print(f"Bandwidth used to access {baseURL}: {bandwidth}")
                        log(f"Bandwidth used to access {baseURL}: {bandwidth}")
                    else:
                        break
                newSock.close()
                cliConn.close

            except socket.error:
                newSock.close()
                cliConn.close()
                sys.exit(1)
            
        # Deals with HTTP that has been stored in cache previously and is not outdated.
        elif cache[baseURL] is not None and cache[baseURL] > datetime.datetime.now():
            print(f"{url} has previously been cached.")
            tic = time.perf_counter()
            info = getCachedVersion(baseURL)
            toc = time.perf_counter()

            print(f"Cache took: {toc - tic:0.4f} seconds to fetch this URL: {baseURL}")
            log(f"Cache took: {toc - tic:0.4f} seconds to fetch this URL: {baseURL}")

            resp = 'HTTP/1.0 200 OK\n\n' + info
            cliConn.send(resp.encode())
        
        # The information cached is outdated and so therefore remove from cache.
        else:
            del cache[baseURL]
                
        newSock.close()
        cliConn.close()

# Get info from cache.
def getCachedVersion(baseURL):
    try:
        readFile = open("C:/Users/mcnam/Documents/GitHub/WebProxyServer/cache/" + baseURL)
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
        if expiry is not None and ("no-cache" in expiry.lower() or "private" in expiry.lower() or "no-store" in expiry.lower()):
            return True

        # Determine when the cached result is no longer useful.
        if expiry is not None and "max-age" in expiry.lower():
            expiry = expiry.split('=')
            expiry = int(expiry[1])
            currTime = datetime.datetime.now()
            # Adds the amount of seconds to the current time.
            expiry = currTime + datetime.timedelta(0,expiry)
        
        # Adds the baseURL as the key to the cache dictionary along with the time its due to 
        # become invalid if that exists.
        cache[baseURL] = expiry
        info = response.read().decode(enc)  
        if info:
            print('Caching: ', cacheFilename)
            try:
                cachedFile = open("C:/Users/mcnam/Documents/GitHub/WebProxyServer/cache/" + baseURL, 'w')
            except Exception as e:
                print(e)
            cachedFile.write(info)
            cachedFile.close()
            return True
        else:
            return False
    except HTTPError:
        return False

# Logs all the information that would be too much to send to the commandline.
def log(input):
    currTime = datetime.datetime.now().strftime("%Y-%m-%d")
    newFile = "Users/mcnam/Documents/GitHub/WebProxyServer/logs/logs_" + str(currTime) + ".txt"
    newFile = newFile.replace(' ', '_')
    newFile = newFile.replace(':', '_')
    newFile = "C:/" + newFile
    file = open(newFile, "a")
    file.write("\n" + input)
    file.flush()


# Starts the proxy server.
startProxy()