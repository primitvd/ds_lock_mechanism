import time
import threading
from client import LockClient

def test_multiple_failures():
    print("\n=== Testing Multiple Node Failures ===")
    
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
        # Client 1 starts operations
        if not client1._acquire_lock():
            raise Exception("Client 1 failed to acquire lock")
            
        # First failure: Server 2 crashes
        print("\nPlease stop Server 2 now...")
        input("Press Enter after stopping Server 2...")
        
        # Client 1 continues operations
        files = ["file_1", "file_2", "file_3", "file_4", "file_5"]
        for file in files:
            client1.append_to_file(file, "A")
            client1.append_to_file(file, "A")
            
        if not client1._release_lock():
            raise Exception("Client 1 failed to release lock")
            
        print("\nPlease restart Server 2 now...")
        input("Press Enter after restarting Server 2...")
        time.sleep(5)  # Allow synchronization
        
        # Second failure: Server 1 and 2 crash
        print("\nPlease stop both Server 1 and Server 2 now...")
        input("Press Enter after stopping both servers...")
        time.sleep(5)
        
        # Try operations during majority failure
        print("Attempting operations during majority failure (should fail)...")
        client2._acquire_lock()  # Expected to fail
        
        print("\nPlease restart Server 1 now...")
        input("Press Enter after restarting Server 1...")
        time.sleep(5)  # Allow leader election
        
        # Resume operations after recovery
        # Client 2 operations
        if not client2._acquire_lock():
            raise Exception("Client 2 failed to acquire lock")
            
        for file in files:
            client2.append_to_file(file, "B")
            client2.append_to_file(file, "B")
            
        if not client2._release_lock():
            raise Exception("Client 2 failed to release lock")
            
        # Client 3 operations
        if not client3._acquire_lock():
            raise Exception("Client 3 failed to acquire lock")
            
        for file in files:
            client3.append_to_file(file, "C")
            client3.append_to_file(file, "C")
            
        if not client3._release_lock():
            raise Exception("Client 3 failed to release lock")
            
        print("\nPlease restart Server 2 now...")
        input("Press Enter after restarting Server 2...")
        time.sleep(5)  # Allow synchronization
        
    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        client1.close()
        client2.close()
        client3.close()
        
    print("\nTest completed. Please verify all files contain 'AABBCC' in the correct order.")

if __name__ == "__main__":
    test_multiple_failures()
