import time
import threading
from client import LockClient

def test_replica_fast_recovery():
    print("\n=== Testing Replica Node Fast Recovery ===")
    
    # Initialize clients
    client1 = LockClient()
    client2 = LockClient()
    
    # Connect clients
    if not client1.initialize() or not client2.initialize():
        print("Failed to initialize clients")
        return
        
    print(f"Client 1 ID: {client1.client_id}")
    print(f"Client 2 ID: {client2.client_id}")
    
    try:
        # Client 1 acquires lock
        if not client1._acquire_lock():
            raise Exception("Client 1 failed to acquire lock")
        
        # Client 1 appends 'A' to first file
        client1.append_to_file("file_1", "A")
        
        # Simulate Server 2 failure (manual step required)
        print("\nPlease stop Server 2 now...")
        input("Press Enter after stopping Server 2...")
        
        # Client 1 continues with second append
        client1.append_to_file("file_2", "A")
        
        print("\nPlease restart Server 2 now...")
        input("Press Enter after restarting Server 2...")
        
        # Client 1 completes final append
        client1.append_to_file("file_3", "A")
        
        # Client 1 releases lock
        if not client1._release_lock():
            raise Exception("Client 1 failed to release lock")
            
        # Client 2 acquires lock
        if not client2._acquire_lock():
            raise Exception("Client 2 failed to acquire lock")
            
        # Client 2 performs appends
        client2.append_to_file("file_1", "B")
        client2.append_to_file("file_2", "B")
        client2.append_to_file("file_3", "B")
        
        # Client 2 releases lock
        if not client2._release_lock():
            raise Exception("Client 2 failed to release lock")
            
    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        client1.close()
        client2.close()
        
    print("\nTest completed. Please verify files contain 'AB' in the correct order.")

if __name__ == "__main__":
    test_replica_fast_recovery()
