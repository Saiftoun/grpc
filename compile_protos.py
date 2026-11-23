#!/usr/bin/env python3
"""
Protocol Buffer Compilation Script

This script compiles the Protocol Buffer definitions for the E-Commerce Microservices project.
It generates Python code from the .proto files in the protos/ directory.

Usage:
    python compile_protos.py

Generated Files:
    - product_pb2.py: Product message classes
    - product_pb2_grpc.py: Product service stub and servicer
    - order_pb2.py: Order message classes
    - order_pb2_grpc.py: Order service stub and servicer
"""

import subprocess
import sys
from pathlib import Path

def compile_protos():
    """Compile Protocol Buffer definitions using grpc_tools.protoc"""
    
    # Ensure we're in the project root
    project_root = Path(__file__).parent
    proto_dir = project_root / "protos"
    
    if not proto_dir.exists():
        print(f"Error: protos/ directory not found at {proto_dir}")
        sys.exit(1)
    
    # Proto files to compile
    proto_files = ["protos/product.proto", "protos/order.proto"]
    
    # Check that proto files exist
    for proto_file in proto_files:
        if not (project_root / proto_file).exists():
            print(f"Error: {proto_file} not found")
            sys.exit(1)
    
    # Compile command
    cmd = [
        sys.executable, "-m", "grpc_tools.protoc",
        "-I./protos",
        "--python_out=.",
        "--grpc_python_out=.",
    ] + proto_files
    
    print(f"Compiling Protocol Buffers...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✓ Protocol Buffers compiled successfully!")
        print(f"Generated files:")
        print(f"  - product_pb2.py")
        print(f"  - product_pb2_grpc.py")
        print(f"  - order_pb2.py")
        print(f"  - order_pb2_grpc.py")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"✗ Error compiling Protocol Buffers:")
        print(e.stderr)
        return 1
    except FileNotFoundError:
        print("✗ Error: grpc_tools.protoc not found.")
        print("Please install dependencies: pip install -r requirements.txt")
        return 1

if __name__ == "__main__":
    sys.exit(compile_protos())
