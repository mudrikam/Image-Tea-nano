import os
import json
import asyncio
from aiohttp import web, WSMsgType
from PySide6.QtCore import QThread, Signal


class TandemServerThread(QThread):
    """
    Background QThread running an aiohttp web server handling:
    1. WebSocket '/ws' for bidirectional JSON messaging with Chrome extensions
       (Auto Flow Batcher and Vector Assist).
    2. HTTP GET '/file?path=...' for streaming downloaded images from Windows disk to Vector Assist.
    """
    server_status_changed = Signal(bool, str)       # is_running, status_message
    worker_status_changed = Signal(str, bool)       # worker_name, is_connected
    log_emitted = Signal(str)                       # message
    file_reported = Signal(str, str, int)           # source, filepath, filesize
    job_reported = Signal(str, str, str)            # event, client, job_id
    batch_completed = Signal(str, list)             # source, filenames list

    def __init__(self, host="127.0.0.1", port=48200, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = port
        self.loop = None
        self.runner = None
        self.site = None
        self.active_sockets = {}    # client_name -> WebSocketResponse
        self._stop_requested = False

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._start_server())
            self.loop.run_forever()
        except Exception as e:
            self.log_emitted.emit(f"Tandem Server exception: {str(e)}")
        finally:
            self.loop.run_until_complete(self._stop_server())
            self.loop.close()

    async def _start_server(self):
        app = web.Application()
        app.router.add_get('/ws', self._handle_ws)
        app.router.add_get('/file', self._handle_file_get)
        app.router.add_options('/file', self._handle_cors_options)

        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port, reuse_address=True)
        await self.site.start()

        msg = f"Running on {self.host}:{self.port}"
        self.server_status_changed.emit(True, msg)
        self.log_emitted.emit(f"Tandem Server started successfully ({self.host}:{self.port})")

    async def _stop_server(self):
        # Close all active websockets
        for name, ws in list(self.active_sockets.items()):
            try:
                await ws.close(code=1000, message=b"Server stopping")
            except Exception:
                pass
        self.active_sockets.clear()

        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()

        self.server_status_changed.emit(False, "Stopped")
        self.worker_status_changed.emit("auto_flow", False)
        self.worker_status_changed.emit("vector_assist", False)
        self.log_emitted.emit("Tandem Server stopped")

    def stop_server(self):
        self._stop_requested = True
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.wait(3000)

    # ─── HTTP File Stream Handler ───────────────────────────────────────────────
    async def _handle_cors_options(self, request):
        return web.Response(
            status=200,
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': '*'
            }
        )

    async def _handle_file_get(self, request):
        file_path = request.query.get('path')
        if not file_path or not os.path.exists(file_path):
            return web.Response(
                status=404,
                text="File not found",
                headers={'Access-Control-Allow-Origin': '*'}
            )

        try:
            # Determine mime type
            ext = os.path.splitext(file_path)[1].lower()
            mime = "image/jpeg"
            if ext in ['.png']:
                mime = "image/png"
            elif ext in ['.webp']:
                mime = "image/webp"
            elif ext in ['.svg']:
                mime = "image/svg+xml"

            with open(file_path, 'rb') as f:
                content = f.read()

            return web.Response(
                body=content,
                content_type=mime,
                headers={'Access-Control-Allow-Origin': '*'}
            )
        except Exception as e:
            return web.Response(
                status=500,
                text=str(e),
                headers={'Access-Control-Allow-Origin': '*'}
            )

    # ─── WebSocket Connection Handler ───────────────────────────────────────────
    async def _handle_ws(self, request):
        ws = web.WebSocketResponse(heartbeat=15.0)
        await ws.prepare(request)

        registered_client = None

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        msg_type = data.get('type') or data.get('event')

                        # 1. Registration handshake
                        if msg_type == 'REGISTER':
                            registered_client = data.get('client')
                            if registered_client:
                                self.active_sockets[registered_client] = ws
                                self.worker_status_changed.emit(registered_client, True)
                                self.log_emitted.emit(f"Worker connected: {registered_client}")
                                await ws.send_json({
                                    "type": "REGISTER_ACK",
                                    "client": registered_client,
                                    "status": "ACCEPTED"
                                })

                        # 2. File Downloaded Report
                        elif msg_type == 'FILE_DOWNLOADED':
                            source = data.get('source', registered_client or 'unknown')
                            filename = data.get('filename', '')
                            file_size = data.get('fileSize', 0)
                            self.file_reported.emit(source, filename, file_size)

                        # 3. Batch Completed Report
                        elif msg_type == 'BATCH_COMPLETED':
                            source = data.get('source', registered_client or 'unknown')
                            filenames = data.get('filenames', [])
                            self.batch_completed.emit(source, filenames)

                        # 4. Heartbeat PING / Keepalive
                        elif msg_type == 'PING':
                            client = data.get('client', registered_client or 'worker')
                            await ws.send_json({
                                "type": "PONG",
                                "client": client
                            })

                        # 5. Job status / error report
                        elif msg_type in ['JOB_ACCEPTED', 'JOB_COMPLETED', 'JOB_ERROR']:
                            client = data.get('client', registered_client)
                            job_id = str(data.get('job_id', ''))
                            self.job_reported.emit(msg_type, client, job_id)
                            if msg_type == 'JOB_ERROR':
                                err_msg = data.get('error', 'Unknown error')
                                self.log_emitted.emit(f"Job error [{job_id}] from {client}: {err_msg}")
                            elif msg_type == 'JOB_COMPLETED':
                                self.log_emitted.emit(f"Job completed [{job_id}] from {client}")

                    except Exception as json_err:
                        self.log_emitted.emit(f"Invalid JSON from websocket: {str(json_err)}")

                elif msg.type == WSMsgType.ERROR:
                    self.log_emitted.emit(f"WebSocket connection error: {ws.exception()}")
        finally:
            if registered_client and registered_client in self.active_sockets:
                del self.active_sockets[registered_client]
                self.worker_status_changed.emit(registered_client, False)
                self.log_emitted.emit(f"Worker disconnected: {registered_client}")

        return ws

    # ─── Outbound Dispatcher Methods ────────────────────────────────────────────
    def send_to_worker(self, worker_name, payload):
        if not self.loop or not self.loop.is_running():
            return False

        ws = self.active_sockets.get(worker_name)
        if not ws or ws.closed:
            return False

        async def _send():
            try:
                await ws.send_json(payload)
                return True
            except Exception as e:
                self.log_emitted.emit(f"Failed to send to {worker_name}: {str(e)}")
                return False

        asyncio.run_coroutine_threadsafe(_send(), self.loop)
        return True

    def dispatch_prompt_to_flow(self, prompt, job_id=None):
        payload = {
            "action": "EXECUTE_PROMPT",
            "job_id": job_id or str(asyncio.get_event_loop_policy().get_event_loop().time() if self.loop else os.urandom(4).hex()),
            "prompt": prompt
        }
        sent = self.send_to_worker("auto_flow", payload)
        if sent:
            self.log_emitted.emit(f"Dispatched prompt to Auto Flow Batcher: \"{prompt}\"")
        else:
            self.log_emitted.emit("WARN: Auto Flow Batcher worker not connected!")
        return sent

    def dispatch_files_to_vector(self, filepaths, job_id=None):
        """Dispatch a batch of image filepaths to Vector Assist worker."""
        if isinstance(filepaths, str):
            filepaths = [filepaths]
        payload = {
            "action": "EXECUTE_FILES",
            "job_id": job_id or os.urandom(4).hex(),
            "filepaths": filepaths
        }
        sent = self.send_to_worker("vector_assist", payload)
        if sent:
            self.log_emitted.emit(f"Dispatched {len(filepaths)} file(s) to Vector Assist")
        else:
            self.log_emitted.emit("Failed to dispatch files to Vector Assist (worker not connected)")
        return sent

    def dispatch_file_to_vector(self, filepath, job_id=None):
        return self.dispatch_files_to_vector([filepath], job_id=job_id)

    def is_worker_connected(self, worker_name):
        ws = self.active_sockets.get(worker_name)
        return bool(ws and not ws.closed)
