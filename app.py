import socket, _thread

max_conn = 5
buffer_size = 8192

def start():
    try:
        s_http = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s_http.bind(('127.0.0.1', 8080))
        s_http.listen(max_conn)
        print("Server started successfully!")
    except Exception as e:
        print(e)
        sys.exit(2)
    
    print("Starting to listen for connections...")
    _thread.start_new_thread(listen, (s_http, 8080))

    while(1):
        one = 1

def listen(s_http, port):
    while(1):
        try:
            conn, _ = s_http.accept()
            data = conn.recv(buffer_size)
            _thread.start_new_thread(decodeRequest, (conn, data, port))
        except Exception as e:
            s_http.close()
            print(e)
            sys.exit(1)

def decodeRequest(conn, data, port):
    try:
        encoding = 'utf-8'
        data = data.decode(encoding)
        first_line = data.split('\n')[0]
        first_line = first_line.split(' ')
        check_method = first_line[0]
        url = first_line[1]
        http_pos = url.find("://")
        print(url)
        if (http_pos == -1):
            tmp = url
        elif check_method == "GET":
            tmp = url[(http_pos+3):]
        else:
            tmp = url[(http_pos+4):]
        
        port_pos = tmp.find(":")

        webserver_pos = tmp.find("/")

        if webserver_pos == -1:
            webserver_pos = len(tmp)
        
        webserver = ""

        port = -1
        if port_pos == -1 or webserver_pos < port_pos:
            port = 80
            webserver = tmp[:webserver_pos]
        
        else:
            port = int((tmp[(port_pos+1):])[:webserver_pos-port_pos-1])
            webserver = tmp[:port_pos]
        
        data = data.encode(encoding)
        proxy_server(webserver, port, conn, data, check_method)
    except Exception as e:
        pass

def proxy_server(webserver, port, conn, data, check_method):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    if check_method == "CONNECT":
        try:
            sock.connect((webserver, port))
            reply = "HTTP/1.0 200 Connection established\r\n"
            reply += "Proxy-agent: Pyx\r\n"
            reply += "\r\n"
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
                print("Request Done: %s => %s <= " % (str(webserver), str(dar)))
            except socket.error as e:
                pass
    else:
        sock.connect((webserver, port))
        sock.send(data)
        try:
            while True:
                reply = sock.recv(buffer_size)
                if (len(reply) > 0):
                    conn.send(reply)
                    dar = float(len(reply))
                    dar = float(dar/1024)
                    dar = "%.3s" % (str(dar))
                    dar = "%s KB" % (dar)
                    print("Request Done: %s => %s <= " % (str(webserver), str(dar)))
                else:
                    break
            sock.close()
            conn.close

        except socket.error:
            sock.close()
            conn.close()
            sys.exit(1)

        sock.close()
        conn.close()

start()
