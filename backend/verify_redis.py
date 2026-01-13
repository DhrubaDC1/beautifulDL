import sys
from cache import RedisCache
import time

def verify():
    print("Connecting to Redis...")
    try:
        cache = RedisCache()
        if cache.ping():
            print("Successfully connected to Redis.")
        else:
            print("Failed to ping Redis.")
            sys.exit(1)
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    # Test Set/Get
    vid = "test_vid"
    fid = "test_fid"
    data = {"filename": "test.mp4", "download_url": "/api/foo"}
    
    print("Testing SET...")
    cache.set(vid, fid, data)
    
    print("Testing GET...")
    retrieved = cache.get(vid, fid)
    
    if retrieved != data:
        print(f"Mismatch! Expected {data}, got {retrieved}")
        sys.exit(1)
    
    print("Data matches.")
    
    print("Testing DELETE...")
    cache.delete(vid, fid)
    if cache.get(vid, fid) is not None:
        print("Delete failed!")
        sys.exit(1)
        
    print("Verification Successful!")

if __name__ == "__main__":
    verify()
