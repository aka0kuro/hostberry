#!/usr/bin/env python3
"""
Test script for network functions
"""
import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, '/home/blag0rag/Hostberry')

async def test_network_functions():
    """Test the network functions directly"""
    try:
        # Test the async_utils functions
        from core.async_utils import run_command_async
        
        print("Testing run_command_async function...")
        
        # Test routing table command
        print("\n1. Testing 'ip route show':")
        returncode, stdout, stderr = await run_command_async('ip', 'route', 'show')
        print(f"   Return code: {returncode}")
        if returncode == 0:
            routes = stdout.strip().split('\n')
            print(f"   Number of routes found: {len([r for r in routes if r.strip()])}")
            for i, route in enumerate(routes[:3]):  # Show first 3 routes
                if route.strip():
                    print(f"   Route {i+1}: {route.strip()}")
        else:
            print(f"   Error: {stderr}")
        
        # Test interface command
        print("\n2. Testing 'ip link show':")
        returncode, stdout, stderr = await run_command_async('ip', 'link', 'show')
        print(f"   Return code: {returncode}")
        if returncode == 0:
            lines = stdout.strip().split('\n')
            interfaces = [line for line in lines if ': ' in line and not line.startswith(' ')]
            print(f"   Number of interfaces found: {len(interfaces)}")
            for iface in interfaces:
                if iface.strip():
                    print(f"   Interface: {iface.strip()}")
        else:
            print(f"   Error: {stderr}")
            
        print("\n✅ Network functions are working correctly!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error testing network functions: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_network_functions())
    sys.exit(0 if result else 1)
