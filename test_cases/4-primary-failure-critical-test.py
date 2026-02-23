import time
import threading
from client import LockClient

def test_primary_failure_critical():
    print("\n=== Testing Primary Node Failure During Critical Section ===")
    
    # Initialize clients
    client1 = LockClient()
    client2 = LockClient()
    client3 = LockClient()
    
    # Connect clients
    if not (client1.initialize() and client2.initialize() and client3.initialize()):
        print("Failed to initialize clients")
        return
        
    print(f"Client IDs: {client1.client_id}, {client2.client_id}, {client3.client_id}")
    
    try:
        # Client 1 operations
        if not client1._acquire_lock():
            raise Exception("Client 1 failed to acquire lock")
            
        # Append 'A' twenty times
        for _ in range(20):
            client1.append_to_file("file_1", "A")
            
        if not client1._release_lock():
            raise Exception("Client 1 failed to release lock")
            
        # Client 2 starts operations
        if not client2._acquire_lock():
            raise Exception("Client 2 failed to acquire lock")
            
        # Append first 10 'B's
        for i in range(10):
            client2.append_to_file("file_1", "B")
            if i == 4:  # Simulate primary failure mid-operation
                print("\nPlease stop Server 1 (primary) now...")
                input("Press Enter after stopping Server 1...")
                time.sleep(5)  # Allow time for new leader election
                
        # Continue with remaining 'B's after primary failure
        for _ in range(10):
            client2.append_to_file("file_1", "B")
            
        if not client2._release_lock():
            raise Exception("Client 2 failed to release lock")
            
        # Client 3 operations
        if not client3._acquire_lock():
            raise Exception("Client 3 failed to acquire lock")
            
        for _ in range(20):
            client3.append_to_file("file_1", "C")
            
        if not client3._release_lock():
            raise Exception("Client 3 failed to release lock")
            
        print("\nPlease restart Server 1 now...")
        input("Press Enter after restarting Server 1...")
        time.sleep(5)  # Allow time for synchronization
        
    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        client1.close()
        client2.close()
        client3.close()
        
    print("\nTest completed. Please verify file contains correct sequence of As, Bs, and Cs.")

if __name__ == "__main__":
    test_primary_failure_critical()
