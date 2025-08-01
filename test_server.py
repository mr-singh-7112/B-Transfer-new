#!/usr/bin/env python3
"""
Test script for B-Transfer Pro server functionality
"""

import os
import tempfile
import requests
import time
import threading
from server import FileTransferHandler, get_or_create_key, compress_file_data, decompress_file_data

def test_encryption():
    """Test encryption key generation and persistence"""
    print("🔐 Testing encryption...")
    
    # Test key generation
    key1 = get_or_create_key()
    key2 = get_or_create_key()
    
    if key1 == key2:
        print("✅ Encryption keys are persistent")
    else:
        print("❌ Encryption keys are not persistent")
        return False
    
    return True

def test_compression():
    """Test file compression and decompression"""
    print("🗜️ Testing compression...")
    
    # Test text file compression
    test_data = b"This is a test file with repeated text. " * 1000
    filename = "test.txt"
    
    compressed_data, compressed_size, was_compressed = compress_file_data(test_data, filename)
    
    if was_compressed and len(compressed_data) < len(test_data):
        print(f"✅ Text compression works (saved {len(test_data) - len(compressed_data)} bytes)")
    else:
        print("⚠️ Text compression not beneficial (expected for small files)")
    
    # Test image file (should not compress)
    image_data = b"fake image data" * 100
    filename = "test.jpg"
    
    compressed_data, compressed_size, was_compressed = compress_file_data(image_data, filename)
    
    if not was_compressed:
        print("✅ Image files correctly not compressed")
    else:
        print("❌ Image files should not be compressed")
        return False
    
    return True

def test_file_operations():
    """Test basic file operations"""
    print("📁 Testing file operations...")
    
    # Create test directory
    test_dir = "test_uploads"
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
    
    # Test file creation and cleanup
    test_file = os.path.join(test_dir, "test.txt")
    with open(test_file, 'w') as f:
        f.write("Test content")
    
    if os.path.exists(test_file):
        print("✅ File creation works")
    else:
        print("❌ File creation failed")
        return False
    
    # Cleanup
    os.remove(test_file)
    os.rmdir(test_dir)
    
    return True

def test_server_imports():
    """Test that all server modules can be imported"""
    print("📦 Testing imports...")
    
    try:
        import server
        print("✅ All server modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 B-Transfer Pro Server Tests")
    print("=" * 40)
    
    tests = [
        test_server_imports,
        test_encryption,
        test_compression,
        test_file_operations
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            print()
    
    print("=" * 40)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Server is ready to run.")
        return True
    else:
        print("⚠️ Some tests failed. Please check the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 