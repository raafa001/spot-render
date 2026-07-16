#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Spot Render - Blender Worker Entrypoint
#
# Worker que processa arquivos 3D e MAXScripts (.ms) e os renderiza no Blender.
#
# Fluxo suportado:
# 1. Arquivos .blend (direto)
# 2. MAXScript .ms + renderlist .xlsx (processa e cria cena no Blender)
# 3. Outros formatos 3D (.fbx, .obj, .gltf) - conversão via Blender
# =============================================================================

WORKER_MODE=${WORKER_MODE:-filesystem}
QUEUE_PATH=${QUEUE_PATH:-/mnt/assets/queue}
INPUT_PATH=${INPUT_PATH:-/mnt/assets/input}
OUTPUT_PATH=${OUTPUT_PATH:-/mnt/assets/output}
PROCESSED_PATH=${PROCESSED_PATH:-/mnt/assets/processed}
FAILED_PATH=${FAILED_PATH:-/mnt/assets/failed}
CONVERTED_PATH=/tmp/converted
RENDERLIST_PATH=${RENDERLIST_PATH:-/mnt/assets/renderlists}
MAX_CONCURRENT_FRAMES=${MAX_CONCURRENT_FRAMES:-1}
LOG_LEVEL=${LOG_LEVEL:-INFO}
POLL_INTERVAL_SECONDS=${POLL_INTERVAL_SECONDS:-30}
METRICS_PORT=${METRICS_PORT:-9100}
BLENDER_PATH=${BLENDER_PATH:-/opt/blender/blender}
MAXSCRIPT_PROCESSOR=/usr/local/bin/maxscript/processor.py
CONVERTER_SCRIPT=/usr/local/bin/converters/convert.py
METRICS_FILE=/tmp/worker_metrics.prom
READY_FILE=/tmp/worker.ready

# Cria diretórios necessários
mkdir -p "${QUEUE_PATH}" "${INPUT_PATH}" "${OUTPUT_PATH}" "${PROCESSED_PATH}" "${FAILED_PATH}" "${CONVERTED_PATH}" "${RENDERLIST_PATH}"

# Garante permissões corretas
chmod -R 0777 "${QUEUE_PATH}" "${INPUT_PATH}" "${OUTPUT_PATH}" "${PROCESSED_PATH}" "${FAILED_PATH}" 2>/dev/null || true

touch "${METRICS_FILE}" "${READY_FILE}"

log() {
  printf '[%s] %s\n' "$(date --iso-8601=seconds)" "$*" >&2
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

# Encontra renderlist correspondente
find_renderlist() {
  local input_file=$1
  local base_name=$(basename "$input_file" .ms)

  # Procura renderlist no mesmo diretório ou no dir de renderlists
  for ext in xlsx xls; do
    # No dir de input
    if [[ -f "${INPUT_PATH}"/*/"${base_name}.${ext}" ]]; then
      echo "${INPUT_PATH}"/*/"${base_name}.${ext}"
      return 0
    fi
    # No dir de renderlists
    if [[ -f "${RENDERLIST_PATH}"/*/"${base_name}.${ext}" ]]; then
      echo "${RENDERLIST_PATH}"/*/"${base_name}.${ext}"
      return 0
    fi
    # Qualquer xlsx no dir de renderlists
    if [[ -f "${RENDERLIST_PATH}"/*.${ext} ]]; then
      echo "${RENDERLIST_PATH}"/*.${ext}
      return 0
    fi
  done
  return 1
}

# Processa arquivo MAXScript com renderlist
process_maxscript() {
  local ms_file=$1
  local output_dir=$2

  log "Processando MAXScript: ${ms_file}"

  # Procura renderlist
  local renderlist=""
  if [[ -d "${INPUT_PATH}" ]] || [[ -d "${RENDERLIST_PATH}" ]]; then
    renderlist=$(find_renderlist "$ms_file")
  fi

  if [[ -n "$renderlist" ]]; then
    log "Renderlist encontrada: ${renderlist}"
  else
    log "Aviso: Nenhuma renderlist encontrada para ${ms_file}"
    log "Criando cena padrão..."
    renderlist="none"
  fi

  # Executa processador de MAXScript
  if python3 "${MAXSCRIPT_PROCESSOR}" "$ms_file" "$renderlist" "$output_dir"; then
    log "MAXScript processado com sucesso"
    return 0
  else
    log "ERRO: Falha no processamento do MAXScript"
    return 1
  fi
}

# Renderiza cena criada
render_blender_scene() {
  local output_dir=$1
  local job_name=$2

  log "Renderizando cena: ${output_dir}"

  # Usa Blender para renderizar a cena atual
  local output_file="${output_dir}/${job_name}_####"

  if "${BLENDER_PATH}" -b \
     -o "${output_file}" \
     -F PNG \
     -x 1 \
     -a \
     -t "${MAX_CONCURRENT_FRAMES}" \
     -- --cycles-device CPU; then
    log "Renderização concluída"
    return 0
  else
    log "ERRO: Blender falhou"
    return 1
  fi
}

# Move arquivo para processados
move_to_processed() {
  local file=$1
  local dest="${PROCESSED_PATH}/$(basename "$file")"
  mv "$file" "$dest" 2>/dev/null && log "Movido para: $dest" || log "Aviso: não foi possível mover"
}

# Move arquivo para falhados
move_to_failed() {
  local file=$1
  local dest="${FAILED_PATH}/$(basename "$file")-$(date +%s)"
  mv "$file" "$dest" 2>/dev/null && log "Movido para failed: $dest" || log "Aviso: não foi possível mover"
}

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

log "Blender worker iniciado"
log "Queue: ${QUEUE_PATH}"
log "Input: ${INPUT_PATH}"
log "Output: ${OUTPUT_PATH}"
log "MAXScript Processor: ${MAXSCRIPT_PROCESSOR}"
log "Blender: ${BLENDER_PATH}"

while true; do
  touch "${READY_FILE}"

  # Procura arquivos na fila
  # Para MAXScript, procura .ms e对应的 xlsx
  mapfile -t queue_files < <(find "${QUEUE_PATH}" -maxdepth 1 -type f -name '*.ms' 2>/dev/null | sort)

  # Também procura arquivos directos na input
  if [[ -d "${INPUT_PATH}" ]]; then
    mapfile -t input_files < <(find "${INPUT_PATH}" -maxdepth 3 -type f \( -name '*.ms' -o -name '*.blend' \) 2>/dev/null | sort)
    # Combina arrays (evita duplicatas)
    for f in "${input_files[@]}"; do
      if [[ ! " ${queue_files[*]} " =~ " ${f} " ]]; then
        queue_files+=("$f")
      fi
    done
  fi

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

  mkdir -p "${job_output_dir}"
  chmod 0777 "${job_output_dir}"

  if (( queue_depth > 0 )); then
    remaining_depth=$((queue_depth - 1))
  else
    remaining_depth=0
  fi

  log "Processando: ${job_path}"

  # Verifica extensão
  ext="${job_name##*.}"
  ext=$(echo "$ext" | tr '[:upper:]' '[:lower:]')

  if [[ "$ext" == "ms" ]]; then
    # Processa MAXScript
    if process_maxscript "${job_path}" "${job_output_dir}"; then
      frames_rendered=$((frames_rendered + 1))
      last_success_ts=$(date +%s)
      update_metrics "${frames_rendered}" "${remaining_depth}" "${last_success_ts}"
      log "Job ${job_name} concluído"
      move_to_processed "${job_path}"
    else
      log "Falha no job ${job_name}"
      move_to_failed "${job_path}"
      update_metrics "${frames_rendered}" "${remaining_depth}" "${last_success_ts}"
    fi

  elif [[ "$ext" == "blend" ]]; then
    # Renderiza .blend direto
    if "${BLENDER_PATH}" -b "${job_path}" \
       -o "${job_output_dir}/frame_#####" \
       -F PNG \
       -x 1 \
       -a \
       -t "${MAX_CONCURRENT_FRAMES}" \
       -- --cycles-device CPU; then
      frames_rendered=$((frames_rendered + 1))
      last_success_ts=$(date +%s)
      log "Job ${job_name} concluído"
      move_to_processed "${job_path}"
    else
      log "Falha no job ${job_name}"
      move_to_failed "${job_path}"
    fi
    update_metrics "${frames_rendered}" "${remaining_depth}" "${last_success_ts}"

  else
    # Outros formatos - tenta converter
    converted_file="${CONVERTED_PATH}/${job_stem}.blend"
    if python3 "${CONVERTER_SCRIPT}" "${job_path}" "${converted_file}"; then
      # Renderiza arquivo convertido
      if "${BLENDER_PATH}" -b "${converted_file}" \
         -o "${job_output_dir}/frame_#####" \
         -F PNG \
         -x 1 \
         -a \
         -t "${MAX_CONCURRENT_FRAMES}" \
         -- --cycles-device CPU; then
        frames_rendered=$((frames_rendered + 1))
        last_success_ts=$(date +%s)
        log "Job ${job_name} concluído"
        move_to_processed "${job_path}"
      else
        log "Falha no job ${job_name}"
        move_to_failed "${job_path}"
      fi
    else
      log "Não foi possível converter ${job_name}"
      move_to_failed "${job_path}"
    fi
    rm -f "${converted_file}" 2>/dev/null || true
    update_metrics "${frames_rendered}" "${remaining_depth}" "${last_success_ts}"
  fi
done
