"""Regenerate gRPC code from middleware/node.proto.   Run from the repo root:

    python -m tools.gen_proto

Run it after ANY change to node.proto and commit the generated files
(middleware/node_pb2.py, middleware/node_pb2_grpc.py). Use the pinned
versions from requirements.txt so everyone's generated code is compatible.
"""
import sys

from grpc_tools import protoc

rc = protoc.main(["protoc", "-I.", "--python_out=.", "--grpc_python_out=.",
                  "middleware/node.proto"])
if rc == 0:
    print("Generated middleware/node_pb2.py and middleware/node_pb2_grpc.py")
sys.exit(rc)
