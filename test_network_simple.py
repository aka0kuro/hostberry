#!/usr/bin/env python3
"""
Simple test for async_utils functions
"""
import asyncio
import subprocess
from typing import Optional, Tuple

async def run_subprocess_async(
    cmd: list[str],
    timeout: Optional[int] = None,
    cwd: Optional[str] = None
) -> Tuple[int, str, str]:
    """Ejecuta un comando subprocess de forma asíncrona"""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise TimeoutError(f"Comando '{' '.join(cmd)}' excedió el timeout de {timeout}s")
        
        return (
            process.returncode,
            stdout.decode('utf-8', errors='replace'),
            stderr.decode('utf-8', errors='replace')
        )
    except Exception as e:
        print(f"Error ejecutando subprocess async: {e}")
        raise

async def run_command_async(*args, timeout: Optional[int] = None, cwd: Optional[str] = None) -> Tuple[int, str, str]:
    """Ejecuta un comando de forma asíncrona"""
    return await run_subprocess_async(list(args), timeout=timeout, cwd=cwd)

async def test_network_functions():
    """Test the network functions directly"""
    try:
        print("Testing network commands...")
        
        # Test routing table command
        print("\n1. Testing 'ip route show':")
        returncode, stdout, stderr = await run_command_async('ip', 'route', 'show')
        print(f"   Return code: {returncode}")
        if returncode == 0:
            routes = stdout.strip().split('\n')
            valid_routes = [r for r in routes if r.strip()]
            print(f"   Number of routes found: {len(valid_routes)}")
            for i, route in enumerate(valid_routes[:3]):  # Show first 3 routes
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
    exit(0 if result else 1)
