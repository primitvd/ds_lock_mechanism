import grpc
import lock_pb2
import lock_pb2_grpc
import time
import threading

class LockClient:
    def __init__(self):
        self.lock_status = False
        self.channel = None
        self.stub = None
        self.client_id = None
        self.append_list = []
        self.server_list = [1,2,3]
        
        self.poll_thread = None
        self.polling = False
        self.got_lock = threading.Event()

    def find_leader(self):
        """Find the current leader by checking each server."""
        for server in self.server_list:
            try:
                channel = grpc.insecure_channel(f'localhost:5005{server}')
                stub = lock_pb2_grpc.LockServiceStub(channel)
                response = stub.announce_leader(lock_pb2.emptyMessage())
                if response.leader_id > 0:
                    self.leader_address = response.leader_id
                    return True
                else: 
                    print("Server has personal issues with his peers. Please try later. Thank You.:)")
                    return False
            except grpc.RpcError:
                pass
        return False

    def initialize(self, resp = 1):
        """Initialize connection with the leader server and get client ID."""
        if not self.find_leader():
            print("Unable to find leader.")
            return False
        
        try:
            self.channel = grpc.insecure_channel(f'localhost:5005{self.leader_address}')
            self.stub = lock_pb2_grpc.LockServiceStub(self.channel)
            client_deets = lock_pb2.Int(rc=0, client_id=self.client_id)
            response = self.stub.client_init(client_deets)
            if response.rc == 0:
                self.client_id = response.client_id
                if resp:
                    print(f"Connected to leader at {self.leader_address}")
                return True
            else:
                if resp:
                    raise Exception("Failed to connect to server")
        except grpc.RpcError:
            return False
        
    def reconnect_to_leader(self):
        if self.find_leader():
            self.initialize()
        else:
            print("Failed to reconnect to the leader.")


    def poll_lock_status(self):
        """Thread function to poll for lock status"""
        print("Waiting for the lock...")
        self.reconnect_to_leader()
        
        while self.polling:
            try:
                response = self.stub.lock_acquire(lock_pb2.lock_args(client_id = self.client_id))
                if response.status == lock_pb2.Status.SUCCESS:
                    print("\nLock granted! You now have the lock.")
                    self.lock_status = True
                    self.got_lock.set()
                    break
                elif response.status == lock_pb2.Status.HOLDS_LOCK:
                    print("Already holds the hold")
                    self.lock_status = True
                    self.got_lock.set()
                    break
                time.sleep(1)
            except grpc.RpcError:
                self.reconnect_to_leader()
                time.sleep(1)
                continue
            
    def start_polling(self):
        self.reconnect_to_leader()
        """Start the polling thread"""
        if self.poll_thread is None or not self.poll_thread.is_alive():
            self.polling = True
            self.got_lock.clear()
            self.poll_thread = threading.Thread(target=self.poll_lock_status)
            self.poll_thread.daemon = True
            self.poll_thread.start()
            
    def stop_polling(self):
        self.reconnect_to_leader()
        """Stop the polling thread"""
        self.polling = False
        if self.poll_thread and self.poll_thread.is_alive():
            self.poll_thread.join()
                    
    def _acquire_lock(self, resp = 1, timeout=None): 
        if self.client_id is None:
            print("Client not initialized")
            return False
        for attempt in range(3):
            try:
                response = self.stub.lock_acquire(lock_pb2.lock_args(client_id=self.client_id))
                print(response)
                if response.status == lock_pb2.Status.SUCCESS:
                    print("Successfully acquired lock")
                    self.lock_status = True
                    return True
                
                if response.status == lock_pb2.Status.WAITING_IN_QUEUE:
                    if resp:
                        print("Added to the wait queue")
                        self.start_polling()
                        got_lock = self.got_lock.wait(timeout=None)
                        if not got_lock:
                            print("Timeout waiting for lock")
                            self.stop_polling()
                    return got_lock

                if response.status == lock_pb2.Status.HOLDS_LOCK:
                    if resp:
                        print(f"{self.client_id}, i.e., you, is current lock owner")
                    self.lock_status = True
                    return True
                print("Failed to acquire lock")
                time.sleep(2)
            except grpc.RpcError:
                self.reconnect_to_leader()
                time.sleep(2)
        return False

    def _release_lock(self):
        if self.client_id is None:
            print("Client not initialized")
            return False
        for attempt in range(3):
            try:
                list = lock_pb2.AppendList(entries=[lock_pb2.FileAppend(filename=item[0],value=item[1]) for item in self.append_list])
                response = self.stub.lock_release(lock_pb2.lock_rel(client_id=self.client_id, list = list))
                if response.status == lock_pb2.Status.DOES_NOT_HOLD_LOCK:
                    print("Lock is not held by client")
                    self.lock_status = False
                    return True
                if response.status == lock_pb2.Status.SUCCESS:
                    print("Successfully released lock")
                    self.lock_status = False
                    return True
                print("Failed to release lock")
                time.sleep(2)
            except grpc.RpcError:
                self.reconnect_to_leader()
                time.sleep(2)
        return False

    def append_to_file(self, filename: str, content: str):
        self.append_list.append([filename,content.encode()])


    def close(self):
        """Clean up client resources and notify server of disconnection."""
        self.stop_polling()
        
        if self.lock_status:
            self._release_lock()
        
        if self.client_id is not None:
            try:
                response = self.stub.client_close(lock_pb2.Int(rc = 0,client_id = self.client_id))
                if response.rc == 0: 
                    print("Successfully closed client connection")

            except grpc.RpcError:
                self.reconnect_to_leader()
        self.channel.close()


def main():
    client = LockClient()
    
    print("\n=== Distributed File Append Client ===")
    print("Connecting to server")
    
    while True:
        while not client.initialize():
            time.sleep(2)
            
        try:
            print("\nClient "+str(client.client_id))
            inp = int(input("1 to acquire lock \n2 to append file \n3 to release lock \n4 to close connection\n"))
            if inp == 1:
                client._acquire_lock()
            
            if inp == 2:
                if not client.lock_status:
                    print("Client does not hold lock")
                    if input("Request for lock?(Y/n)") == "Y":
                        client._acquire_lock()
                filename = input("\nEnter filename (file_XX where XX is 0-99): ").strip()
                if not filename.startswith("file_") or not filename[5:].isdigit():
                    print("[-] Invalid filename format. Must be file_XX where XX is 0-99")
                    continue
                else:
                    content = input("Enter content to append: ")
                    client.append_to_file(filename, content + '\n')
            
            if inp == 3:
                client._release_lock()

            if inp == 4:
                client._release_lock()
                client.close()
                print("Exit")
                exit()
        except Exception as e:
            break

    print("[*] Closing connection...")
    print("[*] Exit")

if __name__ == "__main__":
    main()
