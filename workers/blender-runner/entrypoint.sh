#!/usr/bin/env bash
set -euo pipefail

WORKER_MODE=${WORKER_MODE:-filesystem}
QUEUE_PATH=${QUEUE_PATH:-/mnt/assets/queue}
OUTPUT_PATH=${OUTPUT_PATH:-/mnt/assets/output}
PROCESSED_PATH=${PROCESSED_PATH:-/mnt/assets/completed}
FAILED_PATH=${FAILED_PATH:-/mnt/assets/failed}
MAX_CONCURRENT_FRAMES=${MAX_CONCURRENT_FRAMES:-1}
LOG_LEVEL=${LOG_LEVEL:-INFO}
POLL_INTERVAL_SECONDS=${POLL_INTERVAL_SECONDS:-30}
METRICS_PORT=${METRICS_PORT:-9100}
METRICS_FILE=/tmp/worker_metrics.prom
READY_FILE=/tmp/worker.ready

mkdir -p "${QUEUE_PATH}" "${OUTPUT_PATH}" "${PROCESSED_PATH}" "${FAILED_PATH}"
touch "${METRICS_FILE}" "${READY_FILE}"

log() {
  printf '[%s] %s\n' "$(date --iso-8601=seconds)" "$*" >&2
}

if [[ "${WORKER_MODE}" == "sqs" ]]; then
  log "Worker iniciado em modo SQS"
  exec python3 /usr/local/bin/worker-sqs.py
fi

update_metrics() {
  local frames_total=$1
  local queue_depth=$2
  local last_ts=$3
  cat >"${METRICS_FILE}" <<EOF
# HELP blender_worker_frames_total Frames renderizados pelo worker
# TYPE blender_worker_frames_total counter
blender_worker_frames_total ${frames_total}

# HELP blender_worker_queue_depth Quantidade de arquivos aguardando processamento
# TYPE blender_worker_queue_depth gauge
blender_worker_queue_depth ${queue_depth}

# HELP blender_worker_last_success_timestamp Timestamp Unix do último render
# TYPE blender_worker_last_success_timestamp gauge
blender_worker_last_success_timestamp ${last_ts}
EOF
}

start_metrics_server() {
  python3 - <<'PY' "${METRICS_FILE}" "${METRICS_PORT}" &
import http.server
import os
import sys

METRICS_FILE = sys.argv[1]
PORT = int(sys.argv[2])


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ('/metrics', '/metrics/'):
            self.send_response(404)
            self.end_headers()
            return
        try:
            data = open(METRICS_FILE, 'r', encoding='utf-8').read()
        except FileNotFoundError:
            data = ''
        encoded = data.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; version=0.0.4')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        # Silence default logging
        return


http.server.ThreadingHTTPServer(('', PORT), Handler).serve_forever()
PY
  METRICS_PID=$!
}

cleanup() {
  if [[ -n "${METRICS_PID:-}" ]]; then
    kill "${METRICS_PID}" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

start_metrics_server
frames_rendered=0
last_success_ts=0
update_metrics 0 0 0

log "Blender worker iniciado. Aguardando arquivos em ${QUEUE_PATH}"

while true; do
  touch "${READY_FILE}"
  mapfile -t queue_files < <(find "${QUEUE_PATH}" -maxdepth 1 -type f -name '*.blend' -print | sort)
  queue_depth=${#queue_files[@]}
  if (( queue_depth == 0 )); then
    update_metrics "${frames_rendered}" "${queue_depth}" "${last_success_ts}"
    sleep "${POLL_INTERVAL_SECONDS}"
    continue
  fi

  job_path=${queue_files[0]}
  job_name=$(basename "${job_path}" .blend)
  job_output_dir="${OUTPUT_PATH}/${job_name}"
  mkdir -p "${job_output_dir}"
  chmod 0777 "${job_output_dir}"
  chmod 0777 "${job_output_dir}"
  if (( queue_depth > 0 )); then
    remaining_depth=$((queue_depth - 1))
  else
    remaining_depth=0
  fi

  log "Processando ${job_path} -> ${job_output_dir}"
  if /opt/blender/blender -b "${job_path}" -o "${job_output_dir}/frame_#####" -F PNG -x 1 -a -t "${MAX_CONCURRENT_FRAMES}" \
      -- --cycles-device CUDA --log-file /tmp/blender.log; then
    frames_rendered=$((frames_rendered + 1))
    mv "${job_path}" "${PROCESSED_PATH}/${job_name}.blend"
    last_success_ts=$(date +%s)
    update_metrics "${frames_rendered}" "${remaining_depth}" "${last_success_ts}"
    log "Job ${job_name} concluído com sucesso"
  else
    mv "${job_path}" "${FAILED_PATH}/${job_name}-$(date +%s).blend"
    update_metrics "${frames_rendered}" "${remaining_depth}" "${last_success_ts}"
    log "Falha ao renderizar ${job_name}, arquivo movido para ${FAILED_PATH}"
  fi
done
