#!/bin/bash

GIT_DIR=$(git rev-parse --show-toplevel)

PACKAGE_DIR="$GIT_DIR/src/django_websockets"

PROTO_DIR="$PACKAGE_DIR/transport/proto"

python3.11 -m grpc_tools.protoc -I $PACKAGE_DIR/proto \
    --python_out=$PROTO_DIR --pyi_out=$PROTO_DIR --grpc_python_out=$PROTO_DIR \
    $PACKAGE_DIR/proto/wstransport.proto

sed -i '' "s/import wstransport_pb2 as wstransport__pb2/from . import wstransport_pb2 as wstransport__pb2/g" $PROTO_DIR/wstransport_pb2_grpc.py