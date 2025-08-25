#!/usr/bin/env python3
"""
Simple test script to verify ZamIO deployment
Run this after deployment to check if everything is working
"""

import requests
import sys

def test_endpoint(url, description):
    """Test an endpoint and return status"""
    try:
        response = requests.get(url, timeout=10)
        print(f"✅ {description}: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.text[:200]}...")
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"❌ {description}: {e}")
        return False

def main():
    """Test all endpoints"""
    print("🚀 Testing ZamIO Deployment...")
    print("=" * 50)
    
    # Test endpoints
    endpoints = [
        ("http://localhost:8000/", "Home Page"),
        ("http://localhost:8000/health/", "Health Check"),
        ("http://localhost:8000/admin/", "Admin Panel"),
        ("http://localhost:8000/api/", "API Root"),
    ]
    
    success_count = 0
    total_count = len(endpoints)
    
    for url, description in endpoints:
        if test_endpoint(url, description):
            success_count += 1
        print()
    
    print("=" * 50)
    print(f"📊 Results: {success_count}/{total_count} endpoints working")
    
    if success_count == total_count:
        print("🎉 All endpoints are working! Deployment successful!")
        return 0
    else:
        print("⚠️  Some endpoints failed. Check the logs above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
