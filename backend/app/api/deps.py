from fastapi import Request
from temporalio.client import Client


def get_temporal_client(request: Request) -> Client:
    client: Client = request.app.state.temporal_client
    return client
