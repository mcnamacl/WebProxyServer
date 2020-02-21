import socket, _thread, sys, requests, os
from urllib.request import Request, urlopen, HTTPError

max_conn = 5
buffer_size = 8192
cache = []

def startProxy():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 8080))
        sock.listen(max_conn)
        print("Server started successfully!")
    except Exception as e:
        print(e)
        sys.exit(2)
    
    print("Starting to listen for connections...")
    _thread.start_new_thread(listen, (sock, 8080))

    while(1):
        one = 1

# Listens on port 8080 for requests.
def listen(sock, port):
    while(1):
        try:
            conn, _ = sock.accept()
            data = conn.recv(buffer_size)
            _thread.start_new_thread(decodeRequest, (conn, data, port))
        except Exception as e:
            sock.close()
            print(e)
            sys.exit(1)

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
        
        # Re-encode the data into bytes.
        data = data.encode(encoding)
        proxyServer(baseURL, url, port, conn, data, check_method)
    except Exception as e:
        pass

def proxyServer(baseURL, url, port, conn, data, check_method):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    if check_method == "CONNECT":
        try:
            sock.connect((baseURL, port))
            reply = "HTTP/1.0 200 Connection established\r\nProxy-agent: Claires_Proxy\r\n\r\n"
            conn.sendall(reply.encode())
        except socket.error as e:
            print(e)
            return

        conn.setblocking(0)
        sock.setblocking(0)

        while True:
            try:
                request = conn.recv(buffer_size)
                sock.sendall(request)
            except socket.error as e:
                pass
            try:
                reply = sock.recv(buffer_size)
                conn.sendall(reply)
                dar = float(len(reply))
                dar = float(dar/1024)
                dar = "%.3s" % (str(dar))
                dar = "%s KB" % (dar)
                #print("Request Complete: %s -> %s <- " % (str(baseURL), str(dar)))
            except socket.error as e:
                pass
    else:
        if baseURL not in cache:
            sock.connect((baseURL, port))
            sock.send(data)
            cache.append(baseURL)
            print("This request has not previously been cached.")
            serv_file = fetch_from_server(url)
            if serv_file:
                save_in_cache(url, baseURL, serv_file)

            try:
                while True:
                    reply = sock.recv(buffer_size)
                    if (len(reply) > 0):
                        conn.send(reply)
                        dar = float(len(reply))
                        dar = float(dar/1024)
                        dar = "%.3s" % (str(dar))
                        dar = "%s KB" % (dar)
                        #print("Request Complete: %s -> %s <- " % (str(baseURL), str(dar)))
                    else:
                        break
                sock.close()
                conn.close

            except socket.error:
                sock.close()
                conn.close()
                sys.exit(1)
        
        else:
            content = fetch_from_cache(baseURL)
            print(content)
            resp = 'HTTP/1.0 200 OK\n\n' + content
            conn.send(resp.encode())
            
    sock.close()
    conn.close()

def fetch_from_cache(baseURL):
    try:
        # Check if we have this file locally
        fin = open(baseURL)
        content = fin.read()
        fin.close()
        # If we have it, let's send it
        return content
    except IOError:
        return None


def fetch_from_server(filename):
    q = Request(filename)
    try:
        response = urlopen(q)
        # Grab the header and content from the server req
        response_headers = response.info()
        content = response.read().decode('utf-8')
        return content
    except HTTPError:
        return None


def save_in_cache(filename, baseURL, content):
    print('Saving a copy of {} in the cache'.format(filename))
    try:
        cached_file = open(baseURL, 'w')
    except Exception as e:
        print(e)
    cached_file.write(content)
    cached_file.close()


startProxy()
