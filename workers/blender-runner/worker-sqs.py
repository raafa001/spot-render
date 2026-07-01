#!/usr/bin/env python3
"""
Spot Render - Blender Worker (SQS Consumer)

Worker que consome jobs da fila SQS e executa renderização Blender.
Alternativa ao worker de filesystem para produção em larga escala.

Uso:
    # Com SQS
    python worker-sqs.py

    # Com fila local (desenvolvimento)
    python worker-sqs.py --local-queue

Variáveis de ambiente:
    - SQS_QUEUE_URL: URL da fila SQS (ex: http://localhost:4566/queue/spot-render-jobs)
    - SQS_DLQ_URL: URL da DLQ (opcional)
    - AWS_REGION: Região AWS (padrão: us-east-1)
    - AWS_ACCESS_KEY_ID: Chave de acesso AWS
    - AWS_SECRET_ACCESS_KEY: Chave secreta AWS
    - OUTPUT_PATH: Caminho para outputs (padrão: /mnt/assets/output)
    - PROCESSED_PATH: Caminho para arquivos processados (padrão: /mnt/assets/completed)
    - FAILED_PATH: Caminho para arquivos com falha (padrão: /mnt/assets/failed)
    - BLENDER_PATH: Caminho do Blender (padrão: /opt/blender/blender)
    - MAX_CONCURRENT_FRAMES: Frames simultâneos (padrão: 1)
    - API_URL: URL da API para updates (padrão: http://localhost:8080)
    - METRICS_PORT: Porta do servidor de métricas (padrão: 9100)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import boto3
import requests
from botocore.exceptions import ClientError

# Configuração de logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class JobConfig:
    """Configuração do worker."""
    # SQS
    sqs_queue_url: Optional[str] = None
    sqs_dlq_url: Optional[str] = None
    aws_region: str = "us-east-1"
    aws_endpoint_url: Optional[str] = None

    # Paths
    output_path: str = "/mnt/assets/output"
    processed_path: str = "/mnt/assets/completed"
    failed_path: str = "/mnt/assets/failed"

    # Blender
    blender_path: str = "/opt/blender/blender"
    max_concurrent_frames: int = 1
    render_device: str = "CPU"

    # API
    api_url: str = "http://localhost:8080"
    api_update_interval: int = 30  # segundos

    # Métricas
    metrics_port: int = 9100

    # Área de trabalho temporária
    working_dir: str = "/tmp/spot-render-worker"

    # Local queue (desenvolvimento)
    local_queue_enabled: bool = False
    local_queue_path: str = "/mnt/assets/queue"


@dataclass
class JobMessage:
    """Mensagem de job da fila SQS."""
    job_id: str
    project: str
    variation: str
    artist: str
    filename: str
    input_uri: str
    output_uri: str
    priority: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobMessage":
        return cls(
            job_id=data["job_id"],
            project=data["project"],
            variation=data["variation"],
            artist=data["artist"],
            filename=data["filename"],
            input_uri=data["input_uri"],
            output_uri=data["output_uri"],
            priority=data.get("priority", 0),
        )


class MetricsServer:
    """Servidor HTTP simples para métricas Prometheus."""

    def __init__(self, port: int):
        self.port = port
        self.frames_rendered = 0
        self.jobs_processed = 0
        self.jobs_failed = 0
        self.last_success_ts = 0
        self.queue_depth = 0

    def update(self, frames_rendered: int, jobs_processed: int, jobs_failed: int, queue_depth: int):
        self.frames_rendered = frames_rendered
        self.jobs_processed = jobs_processed
        self.jobs_failed = jobs_failed
        self.queue_depth = queue_depth
        if jobs_processed > 0:
            self.last_success_ts = int(time.time())

    def generate_prometheus(self) -> str:
        return f"""# HELP blender_worker_frames_total Frames renderizados pelo worker
# TYPE blender_worker_frames_total counter
blender_worker_frames_total {self.frames_rendered}

# HELP blender_worker_jobs_total Jobs processados pelo worker
# TYPE blender_worker_jobs_total counter
blender_worker_jobs_total {self.jobs_processed}

# HELP blender_worker_jobs_failed Jobs com falha
# TYPE blender_worker_jobs_failed counter
blender_worker_jobs_failed {self.jobs_failed}

# HELP blender_worker_queue_depth Quantidade de jobs na fila
# TYPE blender_worker_queue_depth gauge
blender_worker_queue_depth {self.queue_depth}

# HELP blender_worker_last_success_timestamp Timestamp do último job bem sucedido
# TYPE blender_worker_last_success_timestamp gauge
blender_worker_last_success_timestamp {self.last_success_ts}
"""


class SQSWorker:
    """Worker que consome jobs da fila SQS."""

    def __init__(self, config: JobConfig):
        self.config = config
        self.running = True
        self.metrics = MetricsServer(config.metrics_port)
        self.sqs_client = None
        self._local_queue: list[JobMessage] = []

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

        # Cria diretórios
        self._ensure_directories()

    def _handle_shutdown(self, signum, frame):
        logger.info("Shutdown solicitado, finalizando...")
        self.running = False

    def _ensure_directories(self):
        """Cria diretórios necessários."""
        for path in [self.config.output_path, self.config.processed_path, self.config.failed_path, self.config.working_dir]:
            Path(path).mkdir(parents=True, exist_ok=True)
        if self.config.local_queue_enabled:
            Path(self.config.local_queue_path).mkdir(parents=True, exist_ok=True)

    def _get_sqs_client(self):
        """Retorna cliente SQS configurado."""
        if self.sqs_client is None:
            self.sqs_client = boto3.client(
                "sqs",
                region_name=self.config.aws_region,
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                endpoint_url=self.config.aws_endpoint_url,
            )
        return self.sqs_client

    def _receive_message(self) -> Optional[tuple[JobMessage, str]]:
        """
        Recebe uma mensagem da fila.

        Returns:
            Tupla (JobMessage, receipt_handle) ou None se fila vazia.
        """
        if self.config.local_queue_enabled:
            if self._local_queue:
                return self._local_queue.pop(0), "local"
            return None

        if not self.config.sqs_queue_url:
            logger.error("SQS_QUEUE_URL não configurado")
            time.sleep(5)
            return None

        try:
            client = self._get_sqs_client()
            response = client.receive_message(
                QueueUrl=self.config.sqs_queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,
                MessageAttributeNames=["All"],
                VisibilityTimeout=300,
            )

            messages = response.get("Messages", [])
            if not messages:
                return None

            message = messages[0]
            body = json.loads(message["Body"])
            job = JobMessage.from_dict(body)
            return job, message["ReceiptHandle"]

        except ClientError as e:
            logger.error(f"Erro ao receber mensagem do SQS: {e}")
            return None

    def _delete_message(self, receipt_handle: str):
        """Deleta mensagem da fila após processamento."""
        if self.config.local_queue_enabled:
            return

        try:
            client = self._get_sqs_client()
            client.delete_message(
                QueueUrl=self.config.sqs_queue_url,
                ReceiptHandle=receipt_handle,
            )
        except ClientError as e:
            logger.error(f"Erro ao deletar mensagem do SQS: {e}")

    def _move_to_dlq(self, job: JobMessage, error: str):
        """Move job para DLQ após falhas."""
        logger.warning(f"Job {job.job_id} movido para DLQ: {error}")
        # O SQS move automaticamente via redrive policy
        # Aqui só registramos o erro

    def _download_input(self, job: JobMessage) -> Optional[Path]:
        """
        Baixa arquivo de input do S3 ou copia do filesystem local.

        Returns:
            Path do arquivo baixado ou None se falhou.
        """
        input_path = Path(self.config.working_dir) / f"input_{job.job_id}"

        if job.input_uri.startswith("s3://"):
            # Download do S3
            try:
                import boto3.resource
                s3 = boto3.resource("s3")

                # Parse s3://bucket/key
                uri_parts = job.input_uri.replace("s3://", "").split("/", 1)
                bucket = uri_parts[0]
                key = uri_parts[1] if len(uri_parts) > 1 else ""

                logger.info(f"Baixando {job.input_uri}...")
                s3.Bucket(bucket).download_file(key, str(input_path))
                return input_path

            except ClientError as e:
                logger.error(f"Erro ao baixar do S3: {e}")
                return None

        elif job.input_uri.startswith("file://"):
            # Copy de arquivo local
            local_path = Path(job.input_uri.replace("file://", ""))
            if local_path.exists():
                shutil.copy(local_path, input_path)
                return input_path
            else:
                logger.error(f"Arquivo local não encontrado: {local_path}")
                return None

        else:
            logger.error(f"URI não suportada: {job.input_uri}")
            return None

    def _upload_output(self, job: JobMessage, output_dir: Path):
        """Upload dos arquivos renderizados para S3 ou filesystem."""
        if job.output_uri.startswith("s3://"):
            try:
                import boto3.resource
                s3 = boto3.resource("s3")

                uri_parts = job.output_uri.replace("s3://", "").split("/", 1)
                bucket = uri_parts[0]
                prefix = uri_parts[1] if len(uri_parts) > 1 else ""

                for file_path in output_dir.rglob("*"):
                    if file_path.is_file():
                        key = f"{prefix}/{file_path.name}"
                        logger.info(f"Enviando {file_path} para {job.output_uri}")
                        s3.Bucket(bucket).upload_file(str(file_path), key)

            except ClientError as e:
                logger.error(f"Erro ao fazer upload para S3: {e}")

        # Para filesystem local, os arquivos já estão no lugar certo

    def _finalize_original(self, job: JobMessage, success: bool):
        if not job.input_uri.startswith("file://"):
            return
        src = Path(job.input_uri.replace("file://", ""))
        dest_root = Path(self.config.processed_path if success else self.config.failed_path)
        dest_root.mkdir(parents=True, exist_ok=True)
        if not src.exists():
            return
        suffix = "completed" if success else "failed"
        dest = dest_root / f"{Path(job.filename).stem}_{suffix}_{int(time.time())}{src.suffix}"
        try:
            shutil.move(src, dest)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falha ao mover arquivo original %s: %s", src, exc)

    def _update_api_progress(self, job: JobMessage, progress: int, total: int, status: str = "running", error_message: str | None = None):
        """Atualiza progresso do job na API."""
        try:
            url = f"{self.config.api_url}/jobs/{job.job_id}/progress"
            data = {
                "frames_rendered": progress,
                "frames_total": total,
                "status": status,
            }
            if error_message:
                data["error_message"] = error_message
            resp = requests.patch(url, json=data, timeout=5)
            if resp.status_code >= 400:
                logger.warning("API retornou %s ao atualizar job %s: %s", resp.status_code, job.job_id, resp.text)
        except requests.RequestException as e:
            logger.debug(f"Erro ao atualizar API (não crítico): {e}")

    def _process_job(self, job: JobMessage) -> bool:
        """
        Processa um job de renderização.

        Returns:
            True se bem succeeded, False se falhou.
        """
        job_name = Path(job.filename).stem
        if job.output_uri.startswith("file://"):
            output_dir = Path(job.output_uri.replace("file://", ""))
        else:
            output_dir = Path(self.config.output_path) / f"{job.project}_{job.variation}_{job_name}_{job.job_id[:8]}"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Download input
        input_file = self._download_input(job)
        if not input_file:
            return False

        try:
            # Atualiza API para running
            self._update_api_progress(job, 0, 100, "running")

            # Executa Blender
            blender_args = [
                self.config.blender_path,
                "-b", str(input_file),
                "-o", f"{output_dir}/frame_#####",
                "-F", "PNG",
                "-x", "1",
                "-a",
                "-t", str(self.config.max_concurrent_frames),
                "--",
                "--cycles-device",
                self.config.render_device,
            ]

            logger.info(f"Iniciando render: {' '.join(blender_args)}")

            import subprocess
            result = subprocess.run(
                blender_args,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hora max
            )

            if result.returncode == 0:
                # Sucesso
                self._upload_output(job, output_dir)
                self._update_api_progress(job, 100, 100, "completed")
                self._finalize_original(job, True)
                return True
            else:
                logger.error(f"Blender falhou: {result.stderr}")
                err = result.stderr.strip() or "Blender retornou código diferente de zero"
                self._update_api_progress(job, 0, 100, "failed", error_message=err[:200])
                self._finalize_original(job, False)
                return False

        except Exception as e:
            logger.error(f"Erro ao processar job {job.job_id}: {e}")
            self._update_api_progress(job, 0, 100, "failed", error_message=str(e)[:200])
            self._finalize_original(job, False)
            return False

        finally:
            # Limpa arquivo de input
            if input_file.exists():
                input_file.unlink()

    def _load_local_queue(self):
        """Carrega jobs da fila local (filesystem)."""
        queue_path = Path(self.config.local_queue_path)
        if not queue_path.exists():
            return

        for file_path in queue_path.glob("*.blend"):
            job = JobMessage(
                job_id=f"local_{file_path.stem}_{int(time.time())}",
                project="local",
                variation="v1",
                artist="local",
                filename=file_path.name,
                input_uri=f"file://{file_path}",
                output_uri=f"file://{self.config.output_path}/{file_path.stem}",
            )
            self._local_queue.append(job)

    def run(self):
        """Loop principal do worker."""
        logger.info("Worker SQS iniciado")
        logger.info(f"Configuração: SQS={not self.config.local_queue_enabled}, API={self.config.api_url}")

        if self.config.local_queue_enabled:
            logger.info(f"Modo local ativo, fila: {self.config.local_queue_path}")

        frames_rendered = 0
        jobs_processed = 0
        jobs_failed = 0

        while self.running:
            try:
                # Carrega fila local se habilitado
                if self.config.local_queue_enabled:
                    self._load_local_queue()

                # Obtém profundidade da fila
                queue_depth = len(self._local_queue)
                if not self.config.local_queue_enabled and self.config.sqs_queue_url:
                    try:
                        client = self._get_sqs_client()
                        attrs = client.get_queue_attributes(
                            QueueUrl=self.config.sqs_queue_url,
                            AttributeNames=["ApproximateNumberOfMessages"],
                        )
                        queue_depth = int(attrs["Attributes"]["ApproximateNumberOfMessages"])
                    except ClientError:
                        pass

                self.metrics.update(frames_rendered, jobs_processed, jobs_failed, queue_depth)

                # Recebe mensagem
                result = self._receive_message()
                if not result:
                    continue

                job, receipt_handle = result

                logger.info(f"Processando job {job.job_id}: {job.filename}")

                # Processa job
                success = self._process_job(job)

                if success:
                    jobs_processed += 1
                    frames_rendered += 1
                    logger.info(f"Job {job.job_id} concluído com sucesso")
                else:
                    jobs_failed += 1
                    self._move_to_dlq(job, "Erro no processamento")
                    logger.error(f"Job {job.job_id} falhou")

                # Deleta mensagem da fila
                self._delete_message(receipt_handle)

            except Exception as e:
                logger.error(f"Erro no loop principal: {e}")
                time.sleep(5)

        logger.info("Worker finalizado")


def main():
    """Entry point."""
    config = JobConfig(
        sqs_queue_url=os.getenv("SQS_QUEUE_URL"),
        sqs_dlq_url=os.getenv("SQS_DLQ_URL"),
        aws_region=os.getenv("AWS_REGION", "us-east-1"),
        aws_endpoint_url=os.getenv("AWS_ENDPOINT_URL"),
        output_path=os.getenv("OUTPUT_PATH", "/mnt/assets/output"),
        processed_path=os.getenv("PROCESSED_PATH", "/mnt/assets/completed"),
        failed_path=os.getenv("FAILED_PATH", "/mnt/assets/failed"),
        blender_path=os.getenv("BLENDER_PATH", "/opt/blender/blender"),
        max_concurrent_frames=int(os.getenv("MAX_CONCURRENT_FRAMES", "1")),
        render_device=os.getenv("BLENDER_RENDER_DEVICE", "CPU").upper(),
        api_url=os.getenv("API_URL", "http://localhost:8080"),
        metrics_port=int(os.getenv("METRICS_PORT", "9100")),
        working_dir=os.getenv("WORKER_TEMP_DIR", "/tmp/spot-render-worker"),
        local_queue_enabled=os.getenv("LOCAL_QUEUE_ENABLED", "false").lower() == "true",
        local_queue_path=os.getenv("QUEUE_PATH", "/mnt/assets/queue"),
    )

    worker = SQSWorker(config)
    worker.run()


if __name__ == "__main__":
    main()
