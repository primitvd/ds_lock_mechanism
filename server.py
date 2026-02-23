# pylint: disable=no-member

import random
import grpc
import lock_pb2
import lock_pb2_grpc
import threading
import  queue
import time
import os
from concurrent import futures

import sys
import json


import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class LockService(lock_pb2_grpc.LockServiceServicer):

    def __init__(self,server_id):
        

        self.file_path = f"server_files_{server_id}"
        self.lock = threading.Lock()
        logger.info(f"Timeout for 1 seconds")
        time.sleep(1)
        self.role = 'follower'
        self.id = server_id
        self.term = 0
        self.leader_id = None
        self.last_heartbeat_time = time.time()

        self.log = []

        self.last_log_index = 0

        self.wait_queue = []
        self.current_lock_owner = None
        self.connected_clients = set()
        self.next_client_id = 1

        self.time_limit = 60

        self.state_file = f"server_state{self.id}.json"

        self.server_list = [1,2,3]
        self.server_list_index = -1

        self.active_server = {
                            1:True,
                            2:True,
                            3:True
                            }
        
        if os.path.exists(self.state_file):
            print("Previous state found, loading...")
            self.load_state()
        else:
            print("Starting fresh server instance...")
            os.makedirs(f"server_files_{server_id}", exist_ok=True)
            for i in range(100):
                with open(os.path.join(f"server_files_{server_id}", f"file_{i}"), 'w') as f:
                    f.write(f"This is file number {i}")
            self.save_state()

        self.halt_operation = False

    def load_state(self):
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            self.current_lock_owner = state['current_lock_owner']
            self.connected_clients = set(state['connected_clients'])
            self.next_client_id = state["next_client_id"]
            self.wait_queue = state['wait_queue']
            self.log = state['log']


        except Exception as e:
            print(f"Error loading state {e}")
            self.current_lock_owner = None
            self.connected_clients = set()
            self.next_client_id = 1
            self.wait_queue = []
            self.log = []

    def save_state(self):        
        state = {
            'current_lock_owner': self.current_lock_owner,
            'connected_clients' : list(self.connected_clients),
            'next_client_id'    : self.next_client_id,
            'wait_queue'        : self.wait_queue,
            'log'               : self.log
            }
        
        try:
            temp_state_file = self.state_file + ".tmp"
            with open(temp_state_file, 'w') as f:
                json.dump(state, f, indent=4)
            os.rename(temp_state_file, self.state_file)
            logger.info("State saved successfully")
        except Exception as e:
            logger.error(f"Error saving state: {e}")


    def background(self):
        while True:
            if self.role == 'follower':
                self.follower()
            else:
                logger.info(f'Leader of term {self.term}')
                self.leader()


    def follower(self):
        logger.info("follower")
        print(f"Server {self.id} is a follower.")
        while self.role == 'follower':
            if time.time() - self.last_heartbeat_time > 0.5:
                self.heartbeats_recieving = 0
                logger.info(time.time() - self.last_heartbeat_time)
                self.find_leader_server()
                time.sleep(random.uniform(1,2))

                logger.info("Follower")
            if self.leader_id != None:
                try:
                    self.match_logs()
                except:
                    pass
                
    def find_leader_server(self):
        if self.heartbeats_recieving == 0:
            if self.server_list_index + 1 == len(self.server_list):
                self.server_list_index = 0
            else:
                self.server_list_index += 1
            
            if self.server_list[self.server_list_index] == self.id:
                self.role = 'leader'
                self.leader_id = self.id
                self.term += 1

    def leader(self):
        while self.role == "leader":
            time.sleep(0.2)
            self.send_heartbeats()

    def send_heartbeats(self):
        # logger.info("func send_heartbeats")
        inactive_servers =  0
        for server in self.server_list:
            if server == self.id:
                continue
            else:
                try:
                    channel = grpc.insecure_channel(f"localhost:5005{server}")
                    stub = lock_pb2_grpc.LockServiceStub(channel)
                    response = stub.heartbeats(lock_pb2.heartbeat_message(term=self.term,leader_id = self.id))
                    self.active_server[server] = True
                    # print(f"Server {self.id} sent heartbeat to {server}")
                except grpc.RpcError as e:
                    inactive_servers += 1
                    if inactive_servers == 2:
                        self.halt_operation = True
                    else:
                        self.halt_operation = False
                    # print(f"Server {self.id} failed to send heartbeat to {server}")
                    pass

    def heartbeats(self, request, context):
        if request.term >= self.term:
            self.term = request.term
            self.leader_id = request.leader_id
            self.heartbeats_recieving = 1
            self.role = "follower"
            self.last_heartbeat_time = time.time()
            # logger.info(self.last_heartbeat_time)
            # print(f"Server {self.id} received heartbeat from server {request.leader_id} in term {request.term}")
            return lock_pb2.emptyMessage()
        

    def match_logs(self):
        try:
            with grpc.insecure_channel(f"localhost:5005{self.leader_id}") as channel:
                stub = lock_pb2_grpc.LockServiceStub(channel)
                response = stub.return_logs(lock_pb2.last_log_index(index = len(self.log)))
                if response:
                    for entry in response.entries:
                        print(entry)
                        if entry.action == 'lock':
                            self.current_lock_owner = int(entry.content)
                            if self.wait_queue:
                                self.wait_queue.pop(0)
                            self.log.append([entry.action,int(entry.content)])
                            # self.timer()
                        if entry.action == 'unlock':
                            self.current_lock_owner = None
                            self.log.append([entry.action,int(entry.content)])
                        if entry.action == 'connect':
                            if int(entry.content) not in self.connected_clients:
                                self.next_client_id += 1
                            self.connected_clients.add(int(entry.content))
                            self.log.append([entry.action,int(entry.content)])
                        if entry.action == 'disconnect':
                            if int(entry.context) in self.connected_clients:
                                self.connected_clients.remove(int(entry.context))
                            self.log.append([entry.action,int(entry.content)])
                        if entry.action == 'wait_queue':
                            self.wait_queue.append(int(entry.content))
                            self.log.append([entry.action,int(entry.content)])
                        if entry.action == 'pop wait_queue':
                            self.wait_queue.pop(0)
                            self.log.append(["pop wait_queue",int(entry.content)])
                        if entry.action[:5] == "file_":
                            with open(os.path.join(self.file_path, entry.action), 'a') as f:
                                f.write(entry.content)
                            self.log.append([entry.action,entry.content])
                        if entry.action == 'None':
                            break
                        self.save_state()
        except:
            pass


    def return_logs(self, request, context):
        try:
            append_list = self.log[request.index:]
            return_list = [lock_pb2.Log(action = str(item[0]),content = str(item[1])) for item in append_list]
            return lock_pb2.Logs(entries = return_list)
        except:
            pass

    def announce_leader(self, request, context):
        if self.halt_operation:
            return lock_pb2.leader_response(leader_id = -1)
        return lock_pb2.leader_response(leader_id = self.leader_id)


# functions to add clients

    def client_init(self,request,context):
        if request.client_id == 0:
            rc = 1
            client_id = self.next_client_id
            self.next_client_id += 1

            threads = []
            for server in self.server_list:
                if server == self.id or self.active_server[server] == False:
                    continue
                thread = threading.Thread(target=self.sc_client_init_server,args= (server,rc,client_id))
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

            self.connected_clients.add(client_id)
            self.log.append(["connect",client_id])
            self.save_state()
            print(f"Client {client_id} connected!")
                
        else:
            rc = 0
            client_id = request.client_id

        return lock_pb2.Int(rc = 0, client_id = client_id)

    def sc_client_init_server(self,server_id,rc,client_id):
        with grpc.insecure_channel(f"localhost:5005{server_id}") as channel:
            stub = lock_pb2_grpc.LockServiceStub(channel)
            time_now = time.time()
            while time.time() - time_now < 4:
                try:
                    response = stub.client_init_sv(lock_pb2.Int(rc = rc, client_id = client_id))
                    if response.rc == 1:
                        logger.info("Saved client init")
                        return True
                    time.sleep(0.5)
                except:
                    pass
            self.active_server[server_id] = False

    def client_init_sv(self,request,context):
        client_id = request.client_id
        self.connected_clients.add(client_id)
        self.log.append(["connect",client_id])
        if request.rc == 1:
            self.next_client_id += 1
        print("updated client")
        self.save_state()
        return lock_pb2.Int(rc = 1, client_id = 0)
    



# functions to close clients

    def client_close(self,request,context):
        client_id = request.client_id
        threads = []
        for server in self.server_list:
            if server == self.id or self.active_server[server] == False:
                continue
            thread = threading.Thread(target=self.sc_client_close_server,args= (server,client_id))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        self.connected_clients.remove(client_id)
        self.log.append(["disconnect",client_id])
        self.save_state()
        print(f"Client {client_id} disconnected!")
                
        return lock_pb2.Int(rc = 0, client_id = client_id)

    def sc_client_close_server(self,server_id,client_id):
        with grpc.insecure_channel(f"localhost:5005{server_id}") as channel:
            stub = lock_pb2_grpc.LockServiceStub(channel)
            time_now = time.time()
            while time.time() - time_now < 4:
                try:
                    response = stub.client_close_sv(lock_pb2.Int(rc = 0,client_id = client_id))
                    if response.rc == 1:
                        logger.info("Client disconnected")
                        return True
                    time.sleep(0.5)
                except:
                    pass
            self.active_server[server_id] = False

    def client_close_sv(self,request,context):
        client_id = request.client_id
        self.connected_clients.remove(client_id)
        self.log.append(["disconnect",client_id])
        print("updated client list")
        self.save_state()
        return lock_pb2.Int(rc = 1, client_id = 0)
    



# functions to acquire lock and to append to lock queue

    def lock_acquire(self, request, context):
        client_id = request.client_id
        with self.lock:
            if self.current_lock_owner is None:
                if self.wait_queue == []:
                    threads = []
                    for server in self.server_list:
                        if server == self.id or self.active_server[server] == False:
                            continue
                        rc = 0
                        thread = threading.Thread(target=self.sc_lock_acquire_server,args= (server,rc,client_id))
                        threads.append(thread)
                        thread.start()

                    for thread in threads:
                        thread.join()
                    self.current_lock_owner = client_id
                    self.timer()
                    self.log.append(["lock",client_id])
                    response = lock_pb2.Response(status = lock_pb2.Status.SUCCESS)
                    self.save_state()
                    return response
            

                if self.wait_queue[0] == client_id:
                    threads = []
                    for server in self.server_list:
                        if server == self.id or self.active_server[server] == False:
                            continue
                        rc = 2
                        thread = threading.Thread(target=self.sc_lock_acquire_server,args= (server,rc,client_id))
                        threads.append(thread)
                        thread.start()

                    for thread in threads:
                        thread.join()
                    self.current_lock_owner = client_id
                    self.timer()
                    self.wait_queue.remove(client_id)
                    self.log.append(["lock",client_id])
                    response = lock_pb2.Response(status = lock_pb2.Status.SUCCESS)
                    self.save_state()
                    return response

            
            if client_id in self.wait_queue:
                response = lock_pb2.Response(status = lock_pb2.Status.WAITING_IN_QUEUE)
                return response
            
            if self.current_lock_owner == client_id:
                response = lock_pb2.Response(status = lock_pb2.Status.HOLDS_LOCK)
                return response

            

        threads = []
        for server in self.server_list:
            if server == self.id or self.active_server[server] == False:
                continue
            rc =1
            thread = threading.Thread(target=self.sc_lock_acquire_server,args= (server,rc,client_id))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()
        self.wait_queue.append(client_id)
        self.log.append(["wait_queue",client_id])
        response = lock_pb2.Response(status = lock_pb2.Status.WAITING_IN_QUEUE)
        self.save_state()
        return response


        
    def sc_lock_acquire_server(self,server_id,rc,client_id):
        with grpc.insecure_channel(f"localhost:5005{server_id}") as channel:
            stub = lock_pb2_grpc.LockServiceStub(channel)
            time_now = time.time()
            while time.time() - time_now < 4:
                try:
                    response = stub.lock_acquire_sv(lock_pb2.Int(rc = rc, client_id = client_id))
                    if response.rc == 1:
                        logger.info("Changed lock owner")
                        return True
                    if response.rc == 2:
                        logger.info("Appended to wait queue")
                        return True
                    time.sleep(0.5)
                except:
                    pass
            self.active_server[server_id] = False

    def lock_acquire_sv(self,request,context):
        client_id = request.client_id
        if request.rc == 0:
            self.current_lock_owner = client_id
            self.log.append(["lock",client_id])
            print("updated lock owner")
            self.save_state()
            return lock_pb2.Int(rc = 1, client_id = 0)
        if request.rc == 1:
            self.wait_queue.append(client_id)
            self.log.append(["wait_queue",client_id])
            print("updated wait queue")
            self.save_state()
            return lock_pb2.Int(rc = 2, client_id = 0)
        if request.rc == 2:
            self.current_lock_owner = client_id
            self.wait_queue.remove(client_id)
            print("updated lock owner")
            self.save_state()
            return lock_pb2.Int(rc = 1, client_id = 0)
        
    def timer(self):
        timer_thread = threading.Thread(target=self.forced_lock_release)
        timer_thread.start()

    def timer_wait_queue(self):
        time.sleep(10)
        if self.current_lock_owner == None and self.wait_queue != []:
            threads = []
            for server in self.server_list:
                if server == self.id or self.active_server[server] == False:
                    continue
                thread = threading.Thread(target=self.sc_pop_queue)
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()
            self.log.append(["pop wait_queue",self.wait_queue[0]])
            if self.current_lock_owner != None:
                self.wait_queue.pop(0)
            self.save_state()
            self.timer_wait_queue()

    def sc_pop_queue(self):
        with grpc.insecure_channel(f"localhost:5005{server_id}") as channel:
            stub = lock_pb2_grpc.LockServiceStub(channel)
            time_now = time.time()
            while time.time() - time_now < 2:
                try:
                    response = stub.pop_queue(lock_pb2.Int(client_id = self.wait_queue[0]))
                    if response.rc == 1:
                        logger.info("Pop queue")
                        return True
                    time.sleep(0.5)
                except:
                    pass
            self.active_server[server_id] = False

    def pop_queue(self,request,context):
        if request.client_id == self.wait_queue[0]:
            self.wait_queue.pop(0)
        self.log.append(["pop wait_queue",request.client_id])
        self.save_state()
        return lock_pb2.Int(rc = 1, client_id = 0)





    def forced_lock_release(self):
        curr_lock_client = self.current_lock_owner
        time.sleep(self.time_limit)
        if curr_lock_client == self.current_lock_owner:
            print("Releasing Lock")
            threads = []
            for server in self.server_list:
                if server == self.id or self.active_server[server] == False:
                    continue
                rc = 0
                client_id = curr_lock_client
                request = lock_pb2.AppendList(entries=[])
                thread = threading.Thread(target=self.sc_lock_release_server,args= (server,client_id, request))
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()
            
            self.log.append(['unlock',self.current_lock_owner])
            self.current_lock_owner = None
            self.save_state()



# functions to release lock

    def lock_release(self,request,context):
        client_id = request.client_id
        files = request.list

        print(files.entries)

        with self.lock:
            if self.current_lock_owner != client_id:
                response = lock_pb2.Response(status=lock_pb2.Status.DOES_NOT_HOLD_LOCK)
                return response
            
            threads = []
            for server in self.server_list:
                if server == self.id or self.active_server[server] == False:
                    continue
                rc = 0
                thread = threading.Thread(target=self.sc_lock_release_server,args= (server,client_id, request))
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

            response = lock_pb2.Response(status = lock_pb2.Status.SUCCESS)
            
            for entry in files.entries:
                if entry.filename == "None":
                    break
                with open(os.path.join(self.file_path, entry.filename), 'a') as f:
                    f.write(entry.value)
                self.log.append([entry.filename,entry.value])

            self.current_lock_owner = None
            # self.timer_wait_queue()
            self.log.append(["unlock",client_id])
            self.save_state()
            return response

    def sc_lock_release_server(self, server_id, client_id, request):
        with grpc.insecure_channel(f"localhost:5005{server_id}") as channel:
            stub = lock_pb2_grpc.LockServiceStub(channel)
            time_now = time.time()
            while time.time() - time_now < 2:
                try:
                    response = stub.lock_release_sv(lock_pb2.lock_rel(client_id = client_id, list = request))
                    if response.rc == 1:
                        logger.info("Released Lock")
                        return True
                    time.sleep(0.5)
                except:
                    pass
            self.active_server[server_id] = False

    def lock_release_sv(self,request,context):
        files = request.list
        for entry in files.entries:
            if entry.filename == "None":
                break
            with open(os.path.join(self.file_path, entry.filename), 'a') as f:
                f.write(entry.value)
            self.log.append([entry.filename,entry.value])
        self.current_lock_owner = None
        self.log.append(["unlock",request.client_id])
        self.save_state()
        return lock_pb2.Int(rc = 1, client_id = 0)
    







    
def serve(server_id):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    lock_service = LockService(server_id)
    lock_pb2_grpc.add_LockServiceServicer_to_server(lock_service, server)

    server.add_insecure_port(f'[::]:5005{server_id}')
    server.start()
    print(f"Lock Server started on port 5005{server_id}")

    threading.Thread(target=lock_service.background).start()

    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        exit()


if __name__ == "__main__":
    server_id = int(sys.argv[1])
    serve(server_id)
