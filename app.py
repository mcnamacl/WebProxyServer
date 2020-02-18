import socket, sys, ssl
import _thread

max_conn = 5
buffer_size = 8192

def start():
    try:
        s_http = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s_http.bind(('127.0.0.1', 8080))
        s_http.listen(max_conn)
        s_https = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s_https.bind(('127.0.0.1'), 8081)
        s_https.listen(max_conn)
        print("Server started successfully!")
    except Exception as e:
        print(e)
        sys.exit(2)
    
    while 1:
        try:
            print("starting sockets")
            conn, addr = s_http.accept()
            data = conn.recv(buffer_size)
            _thread.start_new_thread(conn_string, (conn, data, addr))
            # context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            # context.load_cert_chain(certfile="C:/Users/mcnam/Documents/GitHub/WebProxyServer/cert.pem", keyfile="C:/Users/mcnam/Documents/GitHub/WebProxyServer/key.pem")
            # s_sock = context.wrap_socket(s, server_side=True)
            # conn, addr = s_sock.accept()
            # print("1")
            # data = conn.recv(buffer_size)
            # print("3")
            # _thread.start_new_thread(conn_string, (conn, data, addr))
        except Exception as e:
            s_http.close()
            print(e)
            sys.exit(1)
    
def conn_string(conn, data, addr):
    try:
        print(data)
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
        proxy_server(webserver, port, conn, addr, data, check_method)
    except Exception as e:
        pass

def proxy_server(webserver, port, conn, addr, data, check_method):
    if check_method == "CONNECT":
        # Connect to port 443
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # If successful, send 200 code response
            port = 443
            s.connect(( webserver, port ))
            reply = "CONNECT %s:%s HTTP/1.0\r\nConnection: close\r\n\r\n" % (webserver, port)
            s.sendall( reply.encode() )
        except socket.error as err:
            print(err)
                    
        while True:
            try:
                request = conn.recv(buffer_size)
                s.sendall( request )
            except socket.error as err:
                pass
            try:
                reply = s.recv(buffer_size)
                conn.sendall( reply )
            except socket.error as err:
                pass
        
        s.close()
        conn.close()
    else:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((webserver, port))
            s.send(data)

            while 1:
                reply = s.recv(buffer_size)
                
                if (len(reply)>0):
                    print(reply)
                    conn.send(reply)

                    dar = float(len(reply))
                    dar = float(dar/1024)
                    dar = "%.3s" % (str(dar))
                    dar = "%s KB" % (dar)
                    print("Request Done: %s => %s <= " % (str(addr[0]), str(dar)))

                else:
                    break

        except Exception as e:
            print(e)
            s.close()
            conn.close()
            sys.exit(1)

        s.close()
        conn.close()

start()

