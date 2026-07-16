#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Spot Render - Blender Worker Entrypoint
#
# Worker que processa arquivos 3D (.blend, .ms, .max, .fbx, .obj, etc)
# e os renderiza usando Blender.
#
# Suporta:
# - Arquivos .blend (direto)
# - Arquivos Maya (.ms, .ma) - conversão para .blend via Blender
# - Arquivos 3ds Max (.max) - conversão para .blend via Blender
# - Formatos interop (.fbx, .obj, .gltf, .3ds) - conversão via Blender
# =============================================================================

WORKER_MODE=${WORKER_MODE:-filesystem}
QUEUE_PATH=${QUEUE_PATH:-/mnt/assets/queue}
OUTPUT_PATH=${OUTPUT_PATH:-/mnt/assets/output}
PROCESSED_PATH=${PROCESSED_PATH:-/mnt/assets/processed}
FAILED_PATH=${FAILED_PATH:-/mnt/assets/failed}
CONVERTED_PATH=/tmp/converted
MAX_CONCURRENT_FRAMES=${MAX_CONCURRENT_FRAMES:-1}
LOG_LEVEL=${LOG_LEVEL:-INFO}
POLL_INTERVAL_SECONDS=${POLL_INTERVAL_SECONDS:-30}
METRICS_PORT=${METRICS_PORT:-9100}
BLENDER_PATH=${BLENDER_PATH:-/opt/blender/blender}
CONVERTER_SCRIPT=/usr/local/bin/convert.py
METRICS_FILE=/tmp/worker_metrics.prom
READY_FILE=/tmp/worker.ready

# Extensões suportadas para conversão
SUPPORTED_EXTENSIONS="\.blend$|\.ms$|\.ma$|\.mb$|\.max$|\.fbx$|\.obj$|\.gltf$|\.glb$|\.3ds$"

# Cria diretórios necessários
mkdir -p "${QUEUE_PATH}" "${OUTPUT_PATH}" "${PROCESSED_PATH}" "${FAILED_PATH}" "${CONVERTED_PATH}"

# Garante permissões corretas (0777 para compartilhamento entre containers)
chmod -R 0777 "${QUEUE_PATH}" "${OUTPUT_PATH}" "${PROCESSED_PATH}" "${FAILED_PATH}" 2>/dev/null || true

touch "${METRICS_FILE}" "${READY_FILE}"

log() {
  printf '[%s] %s\n' "$(date --iso-8601=seconds)" "$*" >&2
}

# Verifica se arquivo precisa de conversão
needs_conversion() {
  local file=$1
  local ext="${file##*.}"
  ext=$(echo "$ext" | tr '[:upper:]' '[:lower:]')

  # Se não for .blend, precisa converter
  if [[ "$ext" != "blend" ]]; then
    return 0
  fi
  return 1
}

# Converte arquivo para .blend usando Python converter
convert_file() {
  local input_file=$1
  local output_file=$2

  log "Convertendo ${input_file} -> ${output_file}"

  if python3 "${CONVERTER_SCRIPT}" "${input_file}" "${output_file}"; then
    log "Conversão concluída: ${output_file}"
    return 0
  else
    log "ERRO: Falha na conversão de ${input_file}"
    return 1
  fi
}

# Executa renderização Blender
render_file() {
  local blend_file=$1
  local output_dir=$2

  log "Renderizando ${blend_file} -> ${output_dir}"

  # Verifica se Blender existe
  if [[ ! -x "${BLENDER_PATH}" ]]; then
    log "ERRO: Blender não encontrado em ${BLENDER_PATH}"
    return 1
  fi

  # Executa Blender em background
  if "${BLENDER_PATH}" -b "${blend_file}" \
     -o "${output_dir}/frame_#####" \
     -F PNG \
     -x 1 \
     -a \
     -t "${MAX_CONCURRENT_FRAMES}" \
     -- --cycles-device CPU \
     --log-file /tmp/blender.log 2>&1; then
    log "Renderização concluída"
    return 0
  else
    log "ERRO: Blender falhou"
    return 1
  fi
}

# Move arquivo para diretório de processados
move_to_processed() {
  local file=$1
  local dest="${PROCESSED_PATH}/$(basename "$file")"
  mv "$file" "$dest" 2>/dev/null && log "Movido para: $dest" || log "Aviso: não foi possível mover para $dest"
}

# Move arquivo para diretório de falhados
move_to_failed() {
  local file=$1
  local dest="${FAILED_PATH}/$(basename "$file")-$(date +%s)"
  mv "$file" "$dest" 2>/dev/null && log "Movido para failed: $dest" || log "Aviso: não foi possível mover para $dest"
}

# Atualiza métricas Prometheus
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

# Servidor de métricas HTTP
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

# Modo SQS (usa worker Python)
if [[ "${WORKER_MODE}" == "sqs" ]]; then
  log "Worker iniciado em modo SQS"
  exec python3 /usr/local/bin/worker-sqs.py
fi

# Modo filesystem (processamento direto)
start_metrics_server
frames_rendered=0
last_success_ts=0
update_metrics 0 0 0

log "Blender worker iniciado. Aguardando arquivos em ${QUEUE_PATH}"
log "Converter: ${CONVERTER_SCRIPT}"
log "Blender: ${BLENDER_PATH}"

while true; do
  touch "${READY_FILE}"

  # Procura arquivos na fila (suporta múltiplas extensões)
  mapfile -t queue_files < <(find "${QUEUE_PATH}" -maxdepth 1 -type f \( -name '*.blend' -o -name '*.ms' -o -name '*.ma' -o -name '*.mb' -o -name '*.max' -o -name '*.fbx' -o -name '*.obj' -o -name '*.gltf' -o -name '*.glb' \) 2>/dev/null | sort)

  queue_depth=${#queue_files[@]}
  if (( queue_depth == 0 )); then
    update_metrics "${frames_rendered}" "${queue_depth}" "${last_success_ts}"
    sleep "${POLL_INTERVAL_SECONDS}"
    continue
  fi

  job_path=${queue_files[0]}
  job_name=$(basename "${job_path}")
  job_stem="${job_name%.*}"
  job_output_dir="${OUTPUT_PATH}/${job_stem}"
  job_basename="${job_name%.*}"  # nome sem extensão

  mkdir -p "${job_output_dir}"
  chmod 0777 "${job_output_dir}"

  if (( queue_depth > 0 )); then
    remaining_depth=$((queue_depth - 1))
  else
    remaining_depth=0
  fi

  log "Processando ${job_path}"

  # Verifica se precisa converter
  converted_file=""
  if [[ "${job_name,,}" == *.blend ]]; then
    # Já é .blend, usa direto
    render_input="${job_path}"
  else
    # Precisa converter
    converted_file="${CONVERTED_PATH}/${job_basename}.blend"
    if convert_file "${job_path}" "${converted_file}"; then
      render_input="${converted_file}"
    else
      log "Falha na conversão, movendo para failed: ${job_path}"
      move_to_failed "${job_path}"
      update_metrics "${frames_rendered}" "${remaining_depth}" "${last_success_ts}"
      continue
    fi
  fi

  # Renderiza
  if render_file "${render_input}" "${job_output_dir}"; then
    frames_rendered=$((frames_rendered + 1))
    last_success_ts=$(date +%s)
    update_metrics "${frames_rendered}" "${remaining_depth}" "${last_success_ts}"
    log "Job ${job_name} concluído com sucesso"

    # Move original para processados
    move_to_processed "${job_path}"

    # Se converteu, limpa arquivo convertido
    if [[ -n "${converted_file}" && -f "${converted_file}" ]]; then
      rm -f "${converted_file}"
    fi
  else
    log "Falha ao renderizar ${job_name}"
    move_to_failed "${job_path}"

    # Se converteu, limpa arquivo convertido
    if [[ -n "${converted_file}" && -f "${converted_file}" ]]; then
      rm -f "${converted_file}"
    fi

    update_metrics "${frames_rendered}" "${remaining_depth}" "${last_success_ts}"
  fi
done
