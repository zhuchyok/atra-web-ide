import logging
import asyncio
import os
from typing import Any, Dict, Optional
import grpc
from concurrent import futures

# Импорты будут работать после генерации кода из .proto
# Пока создаем структуру моста
try:
    import agent_protocol_pb2
    import agent_protocol_pb2_grpc
except ImportError:
    agent_protocol_pb2 = None
    agent_protocol_pb2_grpc = None

logger = logging.getLogger("AgentGRPCBridge")

class AgentServiceServicer:
    """
    [SINGULARITY 28.5] gRPC Servicer for Expert Agents.
    Bridges gRPC calls to the local expert_worker logic.
    """
    def __init__(self, worker_callback):
        self.worker_callback = worker_callback

    async def ProcessTask(self, request, context):
        logger.info(f"📡 [gRPC] Received task {request.task_id} for {request.expert_name}")
        
        # Конвертируем Struct в dict
        metadata = dict(request.metadata) if request.metadata else {}
        
        # Вызываем локальную логику воркера
        result = await self.worker_callback({
            "task_id": request.task_id,
            "expert_name": request.expert_name,
            "description": request.description,
            "category": request.category,
            "metadata": metadata
        })
        
        # Формируем ответ
        from google.protobuf.struct_pb2 import Struct
        from google.protobuf.timestamp_pb2 import Timestamp
        import datetime
        
        res_meta = Struct()
        res_meta.update(result.get("metadata", {}))
        
        ts = Timestamp()
        ts.FromDatetime(datetime.datetime.utcnow())
        
        return agent_protocol_pb2.TaskResponse(
            task_id=request.task_id,
            expert_name=request.expert_name,
            status=result.get("status", "success"),
            content=result.get("content", ""),
            reasoning_trace=result.get("reasoning_trace", ""),
            confidence_score=result.get("confidence_score", 0.0),
            metadata=res_meta,
            timestamp=ts
        )

class AgentGRPCServer:
    def __init__(self, worker_callback, port: int = 50051):
        self.port = port
        self.servicer = AgentServiceServicer(worker_callback)
        self.server = None

    async def start(self):
        if not agent_protocol_pb2_grpc:
            logger.error("❌ gRPC code not generated. Cannot start server.")
            return

        self.server = grpc.aio.server()
        agent_protocol_pb2_grpc.add_AgentServiceServicer_to_server(self.servicer, self.server)
        listen_addr = f'[::]:{self.port}'
        self.server.add_insecure_port(listen_addr)
        logger.info(f"🚀 [gRPC] Agent Server starting on {listen_addr}")
        await self.server.start()
        await self.server.wait_for_termination()

    async def stop(self):
        if self.server:
            await self.server.stop(0)
            logger.info("🛑 [gRPC] Agent Server stopped")

def get_grpc_server(worker_callback, port: int = 50051):
    return AgentGRPCServer(worker_callback, port)
