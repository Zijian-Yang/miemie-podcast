#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
VENV_DIR="${ROOT_DIR}/.venv"
SYSTEMD_DIR="${ROOT_DIR}/deploy/systemd"
NPM_CACHE_DIR="${ROOT_DIR}/tmp/npm-cache"
RUNTIME_DIR="${ROOT_DIR}/tmp/runtime"
PID_DIR="${RUNTIME_DIR}/pids"
LOG_DIR="${RUNTIME_DIR}/logs"
APP_SERVICE="miemie-web"
API_SERVICE="miemie-api"
WORKER_SERVICE="miemie-worker"
PLATFORM_NAME="$(uname -s)"

function load_env_file() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    return
  fi
  while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
    local line key value
    line="${raw_line#"${raw_line%%[![:space:]]*}"}"
    if [[ -z "${line}" || "${line}" == \#* || "${line}" != *=* ]]; then
      continue
    fi
    key="${line%%=*}"
    value="${line#*=}"
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    export "${key}=${value}"
  done < "${ENV_FILE}"
}

function refresh_runtime_config() {
  load_env_file
  APP_HOST="${APP_HOST:-0.0.0.0}"
  APP_PORT="${APP_PORT:-3000}"
  APP_DOMAIN="${APP_DOMAIN:-}"
  API_HOST="${API_HOST:-127.0.0.1}"
  API_PORT="${API_PORT:-8000}"
  DATA_DIR="${DATA_DIR:-${ROOT_DIR}/data}"
  DATABASE_URL="${DATABASE_URL:-sqlite:///${DATA_DIR}/miemie.db}"
  QUEUE_BACKEND="${QUEUE_BACKEND:-db_polling}"
  STORAGE_BACKEND="${STORAGE_BACKEND:-local}"
  AUTH_MODE="${AUTH_MODE:-session_single_user}"
  if [[ "${AUTH_MODE}" == "password_single_user" ]]; then
    AUTH_MODE="session_single_user"
  fi
  WORKER_PROCESS_COUNT="${WORKER_PROCESS_COUNT:-2}"
  ANALYSIS_CHUNK_EXTRACT_CONCURRENCY="${ANALYSIS_CHUNK_EXTRACT_CONCURRENCY:-4}"
}

function ensure_runtime_dirs() {
  mkdir -p "${RUNTIME_DIR}" "${PID_DIR}" "${LOG_DIR}" "${NPM_CACHE_DIR}" "${DATA_DIR}"
}

function is_interactive_tty() {
  [[ -t 0 && -t 1 ]]
}

function ensure_interactive_tty() {
  if ! is_interactive_tty; then
    echo "错误：管理脚本为交互式菜单模式，请在交互式终端中直接运行 ./scripts/manage.sh"
    exit 1
  fi
}

function is_ubuntu() {
  [[ -f /etc/os-release ]] && grep -qi '^ID=ubuntu' /etc/os-release
}

function is_macos() {
  [[ "${PLATFORM_NAME}" == "Darwin" ]]
}

function has_systemd() {
  command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]
}

function runtime_mode() {
  if is_macos; then
    echo "macos-local"
  elif is_ubuntu && has_systemd; then
    echo "ubuntu-systemd"
  else
    echo "unsupported"
  fi
}

function is_systemd_mode() {
  [[ "$(runtime_mode)" == "ubuntu-systemd" ]]
}

function is_local_mode() {
  [[ "$(runtime_mode)" == "macos-local" ]]
}

function pause_screen() {
  printf '\n按回车返回菜单...'
  read -r _
}

function run_action_with_pause() {
  set +e
  "$@"
  local status=$?
  set -e
  if [[ "${status}" -ne 0 ]]; then
    echo "操作未成功完成，状态码: ${status}"
  fi
  pause_screen
  return 0
}

function run_action_without_pause() {
  set +e
  "$@"
  local status=$?
  set -e
  if [[ "${status}" -ne 0 ]]; then
    echo "操作未成功完成，状态码: ${status}"
  fi
  return 0
}

function confirm_action() {
  local prompt="$1"
  local answer
  read -r -p "${prompt} [y/N]: " answer
  [[ "${answer}" == "y" || "${answer}" == "Y" ]]
}

function local_pid_file() {
  local service="$1"
  echo "${PID_DIR}/${service}.pid"
}

function local_dev_pid_file() {
  local service="$1"
  echo "${PID_DIR}/${service}.dev.pid"
}

function local_log_file() {
  local service="$1"
  echo "${LOG_DIR}/${service}.log"
}

function is_pid_running() {
  local pid="$1"
  kill -0 "${pid}" 2>/dev/null
}

function read_pid() {
  local service="$1"
  local pid_file
  pid_file="$(local_pid_file "${service}")"
  if [[ -f "${pid_file}" ]]; then
    cat "${pid_file}"
  fi
}

function remove_pid_file() {
  local service="$1"
  local pid_file
  pid_file="$(local_pid_file "${service}")"
  rm -f "${pid_file}"
}

function read_dev_pid() {
  local service="$1"
  local pid_file
  pid_file="$(local_dev_pid_file "${service}")"
  if [[ -f "${pid_file}" ]]; then
    cat "${pid_file}"
  fi
}

function write_dev_pid() {
  local service="$1"
  local pid="$2"
  echo "${pid}" > "$(local_dev_pid_file "${service}")"
}

function remove_dev_pid_file() {
  local service="$1"
  rm -f "$(local_dev_pid_file "${service}")"
}

function get_service_status() {
  local service="$1"
  if is_systemd_mode; then
    local status
    status="$(systemctl is-active "${service}" 2>/dev/null || true)"
    if [[ -n "${status}" ]]; then
      echo "${status}"
    else
      echo "unknown"
    fi
    return
  fi
  if is_local_mode; then
    local pid
    pid="$(read_pid "${service}")"
    if [[ -z "${pid}" ]]; then
      echo "inactive"
      return
    fi
    if is_pid_running "${pid}"; then
      echo "active"
    else
      echo "stale"
    fi
    return
  fi
  echo "unsupported"
}

function print_header() {
  printf '\n================ Miemie Podcast 管理菜单 ================\n'
  printf '项目目录: %s\n' "${ROOT_DIR}"
  printf '运行模式: %s\n' "$(runtime_mode)"
  if [[ -f "${ENV_FILE}" ]]; then
    printf '.env: 已存在\n'
  else
    printf '.env: 未创建\n'
  fi
  printf 'Web: %s:%s\n' "${APP_HOST}" "${APP_PORT}"
  printf 'API: %s:%s\n' "${API_HOST}" "${API_PORT}"
  printf 'Worker 并发: 进程=%s | chunk_extract=%s\n' "${WORKER_PROCESS_COUNT}" "${ANALYSIS_CHUNK_EXTRACT_CONCURRENCY}"
  printf 'APP_DOMAIN: %s\n' "${APP_DOMAIN:-<未设置>}"
  printf '服务状态: %s=%s | %s=%s | %s=%s\n' \
    "${APP_SERVICE}" "$(get_service_status "${APP_SERVICE}")" \
    "${API_SERVICE}" "$(get_service_status "${API_SERVICE}")" \
    "${WORKER_SERVICE}" "$(get_service_status "${WORKER_SERVICE}")"
  printf '=========================================================\n'
}

function ensure_env() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    cp "${ROOT_DIR}/.env.example" "${ENV_FILE}"
    echo "已创建 ${ENV_FILE}，请确认配置后再启动服务。"
  fi
  refresh_runtime_config
}

function ensure_install_supported() {
  local mode
  mode="$(runtime_mode)"
  if [[ "${mode}" == "unsupported" ]]; then
    echo "当前系统暂不支持自动安装。仅支持 Ubuntu(systemd) 与 macOS(local process)。"
    return 1
  fi
}

function ensure_service_management_supported() {
  local mode
  mode="$(runtime_mode)"
  if [[ "${mode}" == "unsupported" ]]; then
    echo "当前系统暂不支持服务管理。仅支持 Ubuntu(systemd) 与 macOS(local process)。"
    return 1
  fi
}

function install_packages_ubuntu() {
  sudo apt-get update
  sudo apt-get install -y python3 python3-venv python3-pip nodejs npm ffmpeg
}

function install_packages_macos() {
  if ! command -v brew >/dev/null 2>&1; then
    echo "macOS 安装依赖需要 Homebrew，请先安装 brew。"
    return 1
  fi
  brew install python node ffmpeg
}

function install_packages() {
  if is_systemd_mode; then
    install_packages_ubuntu
  elif is_local_mode; then
    install_packages_macos
  else
    return 1
  fi
}

function install_python() {
  python3 -m venv "${VENV_DIR}"
  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"
  pip install --upgrade pip
  pip install -e "${ROOT_DIR}/backend"
}

function install_node() {
  ensure_runtime_dirs
  (cd "${ROOT_DIR}" && npm install --cache "${NPM_CACHE_DIR}")
}

function install_playwright() {
  ensure_runtime_dirs
  if is_systemd_mode; then
    (cd "${ROOT_DIR}" && npx playwright install --with-deps chromium)
  else
    (cd "${ROOT_DIR}" && npx playwright install chromium)
  fi
}

function escape_sed_replacement() {
  printf '%s' "$1" | sed -e 's/[\/&]/\\&/g'
}

function node_bin_path() {
  command -v node
}

function node_supports_flag() {
  local flag="$1"
  "$(node_bin_path)" --help 2>/dev/null | grep -Fq -- "${flag}"
}

function node_webstorage_flag() {
  if node_supports_flag "--no-experimental-webstorage"; then
    echo "--no-experimental-webstorage"
  fi
}

function next_cli_path() {
  echo "${ROOT_DIR}/node_modules/next/dist/bin/next"
}

function standalone_server_path() {
  echo "${ROOT_DIR}/apps/web/.next/standalone/apps/web/server.js"
}

function next_cli_shell_prefix() {
  printf '%q ' "$(node_bin_path)"
  local extra_flag
  extra_flag="$(node_webstorage_flag)"
  if [[ -n "${extra_flag}" ]]; then
    printf '%q ' "${extra_flag}"
  fi
  printf '%q' "$(next_cli_path)"
}

function ensure_web_runtime_ready() {
  if [[ ! -d "${ROOT_DIR}/node_modules" ]]; then
    echo "未找到前端依赖，请先执行安装部署。"
    return 1
  fi
  if [[ ! -f "$(next_cli_path)" ]]; then
    echo "未找到 Next.js CLI，请先执行安装部署。"
    return 1
  fi
  if [[ ! -f "${ROOT_DIR}/apps/web/.next/BUILD_ID" ]]; then
    echo "未发现前端构建产物，正在先执行前端重建..."
    command_rebuild_web
  fi
  if [[ ! -f "$(standalone_server_path)" ]]; then
    echo "未发现 standalone 服务入口，正在先执行前端重建..."
    command_rebuild_web
  fi
  if [[ ! -d "${ROOT_DIR}/apps/web/.next/standalone/apps/web/.next/static" ]]; then
    sync_web_standalone_assets
  fi
}

function sync_web_standalone_assets() {
  local standalone_app_dir static_source static_target public_source public_target
  standalone_app_dir="${ROOT_DIR}/apps/web/.next/standalone/apps/web"
  static_source="${ROOT_DIR}/apps/web/.next/static"
  static_target="${standalone_app_dir}/.next/static"
  public_source="${ROOT_DIR}/apps/web/public"
  public_target="${standalone_app_dir}/public"

  if [[ ! -d "${standalone_app_dir}" ]]; then
    echo "未找到 standalone 构建目录，请先执行前端重建。"
    return 1
  fi

  mkdir -p "$(dirname "${static_target}")"
  rm -rf "${static_target}"
  if [[ -d "${static_source}" ]]; then
    cp -R "${static_source}" "${static_target}"
  fi

  if [[ -d "${public_source}" ]]; then
    rm -rf "${public_target}"
    cp -R "${public_source}" "${public_target}"
  fi
}

function render_systemd_unit() {
  local template_path="$1"
  local target_path="$2"
  local root_dir_escaped python_bin_escaped node_bin_escaped node_flag_escaped
  root_dir_escaped="$(escape_sed_replacement "${ROOT_DIR}")"
  python_bin_escaped="$(escape_sed_replacement "${VENV_DIR}/bin/python")"
  node_bin_escaped="$(escape_sed_replacement "$(node_bin_path)")"
  node_flag_escaped="$(escape_sed_replacement "$(node_webstorage_flag)")"
  sed \
    -e "s/__ROOT_DIR__/${root_dir_escaped}/g" \
    -e "s/__PYTHON_BIN__/${python_bin_escaped}/g" \
    -e "s/__NODE_BIN__/${node_bin_escaped}/g" \
    -e "s/__NODE_WEBSTORAGE_FLAG__/${node_flag_escaped}/g" \
    "${template_path}" | sudo tee "${target_path}" >/dev/null
}

function install_systemd() {
  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    echo "未找到 Python 虚拟环境，请先执行安装部署。"
    return 1
  fi
  if ! command -v node >/dev/null 2>&1; then
    echo "未找到 node，请先安装 Node 依赖。"
    return 1
  fi
  render_systemd_unit "${SYSTEMD_DIR}/${APP_SERVICE}.service" "/etc/systemd/system/${APP_SERVICE}.service"
  render_systemd_unit "${SYSTEMD_DIR}/${API_SERVICE}.service" "/etc/systemd/system/${API_SERVICE}.service"
  render_systemd_unit "${SYSTEMD_DIR}/${WORKER_SERVICE}.service" "/etc/systemd/system/${WORKER_SERVICE}.service"
  sudo systemctl daemon-reload
  sudo systemctl enable "${APP_SERVICE}" "${API_SERVICE}" "${WORKER_SERVICE}" >/dev/null
}

function command_rebuild_web() {
  (cd "${ROOT_DIR}" && npm run build:web)
  sync_web_standalone_assets
  echo "前端已重建。"
}

function command_install() {
  ensure_install_supported || return 1
  ensure_env
  ensure_runtime_dirs
  if is_systemd_mode; then
    echo "该操作将在 Ubuntu 上执行安装，并依赖 apt-get、systemd、sudo 权限。"
  else
    echo "该操作将在 macOS 上执行安装，并依赖 Homebrew。"
  fi
  if ! confirm_action "确认继续安装部署吗？"; then
    echo "已取消安装。"
    return 0
  fi
  install_packages
  install_python
  install_node
  install_playwright
  command_rebuild_web
  if is_systemd_mode; then
    install_systemd
  fi
  echo "安装完成。"
}

function start_local_service() {
  local service="$1"
  shift
  local pid_file log_file pid
  pid_file="$(local_pid_file "${service}")"
  log_file="$(local_log_file "${service}")"
  pid="$(read_pid "${service}")"
  if [[ -n "${pid}" ]] && is_pid_running "${pid}"; then
    echo "${service} 已在运行，PID=${pid}"
    return 0
  fi
  remove_pid_file "${service}"
  ensure_runtime_dirs
  (
    cd "${ROOT_DIR}"
    nohup "$@" >>"${log_file}" 2>&1 &
    echo $! > "${pid_file}"
  )
  pid="$(read_pid "${service}")"
  sleep 1
  if [[ -n "${pid}" ]] && is_pid_running "${pid}"; then
    echo "${service} 启动成功，PID=${pid}"
  else
    echo "${service} 启动失败，请检查日志：${log_file}"
    return 1
  fi
}

function ensure_dev_runtime_ready() {
  ensure_env
  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    echo "未找到 Python 虚拟环境，请先执行安装部署。"
    return 1
  fi
  if [[ ! -d "${ROOT_DIR}/node_modules" ]]; then
    echo "未找到前端依赖，请先执行安装部署。"
    return 1
  fi
}

function ensure_port_available() {
  local host="$1"
  local port="$2"
  local label="$3"
  if CHECK_HOST="${host}" CHECK_PORT="${port}" python3 - <<'PY' >/dev/null 2>&1
import socket
import os
host = os.environ["CHECK_HOST"]
port = int(os.environ["CHECK_PORT"])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind((host, port))
except OSError:
    raise SystemExit(1)
finally:
    s.close()
PY
  then
    return 0
  fi
  echo "${label} 端口 ${host}:${port} 已被占用，请先释放端口或修改配置。"
  return 1
}

function run_foreground_command() {
  echo "正在以前台方式运行，按 Ctrl+C 返回主菜单。"
  set +e
  "$@"
  local status=$?
  set -e
  if [[ "${status}" -ne 0 && "${status}" -ne 130 ]]; then
    echo "进程退出异常，状态码: ${status}"
    return "${status}"
  fi
  echo
  echo "已返回主菜单。"
}

function show_dev_endpoints() {
  local web_host api_host
  web_host="$(normalize_origin_host "${APP_HOST}")"
  api_host="$(normalize_origin_host "${API_HOST}")"
  echo "开发模式服务地址："
  echo "- Web 首页: http://${web_host}:${APP_PORT}"
  echo "- API 基础地址: http://${api_host}:${API_PORT}"
  echo "- API 健康检查: http://${api_host}:${API_PORT}/healthz"
  echo "- 详情页示例: http://${web_host}:${APP_PORT}/episodes/<episode_id>"
  echo
  echo "开发模式日志文件："
  echo "- Web: $(local_log_file "${APP_SERVICE}")"
  echo "- API: $(local_log_file "${API_SERVICE}")"
  echo "- Worker: $(local_log_file "${WORKER_SERVICE}")"
}

function run_dev_stack() {
  ensure_dev_runtime_ready || return 1
  ensure_runtime_dirs
  ensure_port_available "${API_HOST}" "${API_PORT}" "API" || return 1
  ensure_port_available "${APP_HOST}" "${APP_PORT}" "Web" || return 1

  local api_log worker_log web_log api_pid worker_pid web_pid
  api_log="$(local_log_file "${API_SERVICE}")"
  worker_log="$(local_log_file "${WORKER_SERVICE}")"
  web_log="$(local_log_file "${APP_SERVICE}")"
  : > "${api_log}"
  : > "${worker_log}"
  : > "${web_log}"

  echo "正在启动开发模式所需服务..."
  (
    cd "${ROOT_DIR}"
    env APP_ENV=development PYTHONUNBUFFERED=1 "${VENV_DIR}/bin/python" -m miemie_podcast.api.app >>"${api_log}" 2>&1 &
    api_pid=$!
    write_dev_pid "${API_SERVICE}" "${api_pid}"
    env APP_ENV=development PYTHONUNBUFFERED=1 "${VENV_DIR}/bin/python" -m miemie_podcast.worker.main >>"${worker_log}" 2>&1 &
    worker_pid=$!
    write_dev_pid "${WORKER_SERVICE}" "${worker_pid}"
    (
      cd "${ROOT_DIR}"
      env APP_ENV=development WATCHPACK_POLLING=true $(next_cli_shell_prefix) dev apps/web --hostname "${APP_HOST}" --port "${APP_PORT}"
    ) >>"${web_log}" 2>&1 &
    web_pid=$!
    write_dev_pid "${APP_SERVICE}" "${web_pid}"

    sleep 2
    if ! is_pid_running "${api_pid}"; then
      echo "API 启动失败，请查看日志：${api_log}"
      wait "${api_pid}" 2>/dev/null || true
      kill "${worker_pid}" "${web_pid}" 2>/dev/null || true
      return 1
    fi
    if ! is_pid_running "${worker_pid}"; then
      echo "Worker 启动失败，请查看日志：${worker_log}"
      kill "${api_pid}" "${web_pid}" 2>/dev/null || true
      wait "${worker_pid}" 2>/dev/null || true
      return 1
    fi
    if ! is_pid_running "${web_pid}"; then
      echo "Web 启动失败，请查看日志：${web_log}"
      kill "${api_pid}" "${worker_pid}" 2>/dev/null || true
      wait "${web_pid}" 2>/dev/null || true
      return 1
    fi

    show_dev_endpoints
    echo "开发模式已启动，按 Ctrl+C 结束所有开发进程并返回菜单。"

    trap 'kill "${api_pid}" "${worker_pid}" "${web_pid}" 2>/dev/null || true; remove_dev_pid_file "${API_SERVICE}"; remove_dev_pid_file "${WORKER_SERVICE}"; remove_dev_pid_file "${APP_SERVICE}"' INT TERM EXIT
    tail -f "${api_log}" "${worker_log}" "${web_log}"
  )
  local status=$?
  if [[ "${status}" -ne 0 && "${status}" -ne 130 ]]; then
    echo "开发模式退出异常，状态码: ${status}"
    return "${status}"
  fi
  echo
  echo "开发模式已停止，已返回主菜单。"
}

function stop_local_dev_service() {
  local service="$1"
  local pid
  pid="$(read_dev_pid "${service}")"
  if [[ -z "${pid}" ]]; then
    echo "${service} 开发进程未运行。"
    return 0
  fi
  if ! is_pid_running "${pid}"; then
    echo "${service} 开发 PID 文件已过期，正在清理。"
    remove_dev_pid_file "${service}"
    return 0
  fi
  kill "${pid}" 2>/dev/null || true
  sleep 1
  if is_pid_running "${pid}"; then
    kill -9 "${pid}" 2>/dev/null || true
  fi
  remove_dev_pid_file "${service}"
  echo "${service} 开发进程已停止。"
}

function stop_local_dev_stack() {
  stop_local_dev_service "${APP_SERVICE}"
  stop_local_dev_service "${WORKER_SERVICE}"
  stop_local_dev_service "${API_SERVICE}"
}

function stop_local_service() {
  local service="$1"
  local pid
  pid="$(read_pid "${service}")"
  if [[ -z "${pid}" ]]; then
    echo "${service} 未运行。"
    return 0
  fi
  if ! is_pid_running "${pid}"; then
    echo "${service} PID 文件已过期，正在清理。"
    remove_pid_file "${service}"
    return 0
  fi
  kill "${pid}" 2>/dev/null || true
  sleep 1
  if is_pid_running "${pid}"; then
    kill -9 "${pid}" 2>/dev/null || true
  fi
  remove_pid_file "${service}"
  echo "${service} 已停止。"
}

function command_start() {
  ensure_service_management_supported || return 1
  ensure_env
  ensure_runtime_dirs
  ensure_web_runtime_ready || return 1
  if is_systemd_mode; then
    install_systemd
    sudo systemctl reset-failed "${APP_SERVICE}" "${API_SERVICE}" "${WORKER_SERVICE}" || true
    sudo systemctl start "${APP_SERVICE}" "${API_SERVICE}" "${WORKER_SERVICE}"
    echo "服务已启动。"
    return 0
  fi
  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    echo "未找到 Python 虚拟环境，请先执行安装部署。"
    return 1
  fi
  if [[ ! -d "${ROOT_DIR}/node_modules" ]]; then
    echo "未找到前端依赖，请先执行安装部署。"
    return 1
  fi
  ensure_port_available "${API_HOST}" "${API_PORT}" "API" || return 1
  ensure_port_available "${APP_HOST}" "${APP_PORT}" "Web" || return 1
  start_local_service "${API_SERVICE}" env APP_ENV=production PYTHONUNBUFFERED=1 "${VENV_DIR}/bin/python" -m miemie_podcast.api.app
  start_local_service "${WORKER_SERVICE}" env APP_ENV=production PYTHONUNBUFFERED=1 "${VENV_DIR}/bin/python" -m miemie_podcast.worker.main
  start_local_service "${APP_SERVICE}" bash -lc "cd \"${ROOT_DIR}\" && env APP_ENV=production HOSTNAME=\"${APP_HOST}\" PORT=\"${APP_PORT}\" \"$(node_bin_path)\" \"$(standalone_server_path)\""
}

function command_stop() {
  ensure_service_management_supported || return 1
  if ! confirm_action "确认停止全部服务吗？"; then
    echo "已取消停止。"
    return 0
  fi
  if is_systemd_mode; then
    sudo systemctl stop "${APP_SERVICE}" "${API_SERVICE}" "${WORKER_SERVICE}"
    echo "服务已停止。"
    return 0
  fi
  stop_local_service "${APP_SERVICE}"
  stop_local_service "${WORKER_SERVICE}"
  stop_local_service "${API_SERVICE}"
}

function command_restart() {
  ensure_service_management_supported || return 1
  if ! confirm_action "确认重启全部服务吗？"; then
    echo "已取消重启。"
    return 0
  fi
  ensure_env
  ensure_runtime_dirs
  ensure_web_runtime_ready || return 1
  if is_systemd_mode; then
    install_systemd
    sudo systemctl reset-failed "${APP_SERVICE}" "${API_SERVICE}" "${WORKER_SERVICE}" || true
    sudo systemctl restart "${APP_SERVICE}" "${API_SERVICE}" "${WORKER_SERVICE}"
    echo "服务已重启。"
    return 0
  fi
  stop_local_service "${APP_SERVICE}"
  stop_local_service "${WORKER_SERVICE}"
  stop_local_service "${API_SERVICE}"
  command_start
}

function command_status_text() {
  ensure_service_management_supported || return 1
  if is_systemd_mode; then
    sudo systemctl status "${APP_SERVICE}" "${API_SERVICE}" "${WORKER_SERVICE}" --no-pager || true
    return 0
  fi
  local service pid status log_file
  for service in "${APP_SERVICE}" "${API_SERVICE}" "${WORKER_SERVICE}"; do
    pid="$(read_pid "${service}")"
    status="$(get_service_status "${service}")"
    log_file="$(local_log_file "${service}")"
    printf '%s: %s' "${service}" "${status}"
    if [[ -n "${pid}" ]]; then
      printf ' (PID=%s)' "${pid}"
    fi
    printf '\n'
    printf '日志: %s\n' "${log_file}"
  done
}

function command_status_json() {
  printf '{"mode":"%s","services":{"%s":"%s","%s":"%s","%s":"%s"}}\n' \
    "$(runtime_mode)" \
    "${APP_SERVICE}" "$(get_service_status "${APP_SERVICE}")" \
    "${API_SERVICE}" "$(get_service_status "${API_SERVICE}")" \
    "${WORKER_SERVICE}" "$(get_service_status "${WORKER_SERVICE}")"
}

function command_logs() {
  ensure_service_management_supported || return 1
  echo "正在查看日志，按 Ctrl+C 返回主菜单。"
  set +e
  if is_systemd_mode; then
    sudo journalctl -u "${APP_SERVICE}" -u "${API_SERVICE}" -u "${WORKER_SERVICE}" -f
  else
    ensure_runtime_dirs
    touch "$(local_log_file "${APP_SERVICE}")" "$(local_log_file "${API_SERVICE}")" "$(local_log_file "${WORKER_SERVICE}")"
    tail -f "$(local_log_file "${APP_SERVICE}")" "$(local_log_file "${API_SERVICE}")" "$(local_log_file "${WORKER_SERVICE}")"
  fi
  local status=$?
  set -e
  if [[ "${status}" -ne 0 && "${status}" -ne 130 ]]; then
    echo "日志查看异常退出，状态码: ${status}"
    return "${status}"
  fi
  echo
  echo "已返回主菜单。"
}

function command_update() {
  ensure_service_management_supported || return 1
  if ! confirm_action "确认拉取最新代码并更新服务吗？"; then
    echo "已取消更新。"
    return 0
  fi
  git -C "${ROOT_DIR}" pull --ff-only origin main
  install_python
  install_node
  install_playwright
  command_rebuild_web
  if is_systemd_mode; then
    install_systemd
    sudo systemctl reset-failed "${APP_SERVICE}" "${API_SERVICE}" "${WORKER_SERVICE}" || true
    sudo systemctl restart "${APP_SERVICE}" "${API_SERVICE}" "${WORKER_SERVICE}"
  else
    stop_local_service "${APP_SERVICE}"
    stop_local_service "${WORKER_SERVICE}"
    stop_local_service "${API_SERVICE}"
    start_local_service "${API_SERVICE}" env APP_ENV=production PYTHONUNBUFFERED=1 "${VENV_DIR}/bin/python" -m miemie_podcast.api.app
    start_local_service "${WORKER_SERVICE}" env APP_ENV=production PYTHONUNBUFFERED=1 "${VENV_DIR}/bin/python" -m miemie_podcast.worker.main
    start_local_service "${APP_SERVICE}" bash -lc "cd \"${ROOT_DIR}\" && env APP_ENV=production HOSTNAME=\"${APP_HOST}\" PORT=\"${APP_PORT}\" \"$(node_bin_path)\" \"$(standalone_server_path)\""
  fi
  echo "项目已更新。"
}

function start_menu() {
  while true; do
    printf '\n---------------- 启动模式选择 ----------------\n'
    printf '1. 生产模式启动（守护运行）\n'
    printf '2. 开发模式一键启动（Web + API + Worker）\n'
    printf '3. 停止所有开发模式进程\n'
    printf '4. 返回主菜单\n'
    printf '请选择操作 [1-4]: '
    local choice
    read -r choice
    case "${choice}" in
      1) run_action_with_pause command_start; return 0 ;;
      2) run_action_without_pause run_dev_stack; return 0 ;;
      3) run_action_with_pause stop_local_dev_stack; return 0 ;;
      4) return 0 ;;
      *) echo "无效选择，请重新输入。"; pause_screen ;;
    esac
  done
}

function print_current_config() {
  cat <<EOF
APP_HOST=${APP_HOST}
APP_PORT=${APP_PORT}
APP_DOMAIN=${APP_DOMAIN}
API_HOST=${API_HOST}
API_PORT=${API_PORT}
WEB_ORIGIN=${WEB_ORIGIN:-}
NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL:-}
DATA_DIR=${DATA_DIR}
DATABASE_URL=${DATABASE_URL}
QUEUE_BACKEND=${QUEUE_BACKEND}
STORAGE_BACKEND=${STORAGE_BACKEND}
AUTH_MODE=${AUTH_MODE}
WORKER_PROCESS_COUNT=${WORKER_PROCESS_COUNT}
ANALYSIS_CHUNK_EXTRACT_CONCURRENCY=${ANALYSIS_CHUNK_EXTRACT_CONCURRENCY}
EOF
}

function write_env_value() {
  local key="$1"
  local value="$2"
  local stored_value="${value}"
  ensure_env
  if [[ "${value}" =~ [[:space:]#] ]]; then
    stored_value="\"${value}\""
  fi
  local tmp_file
  tmp_file="$(mktemp)"
  awk -v key="${key}" -v value="${stored_value}" '
    BEGIN { updated = 0 }
    $0 ~ ("^" key "=") {
      print key "=" value
      updated = 1
      next
    }
    { print $0 }
    END {
      if (updated == 0) {
        print key "=" value
      }
    }
  ' "${ENV_FILE}" > "${tmp_file}"
  mv "${tmp_file}" "${ENV_FILE}"
  refresh_runtime_config
}

function normalize_origin_host() {
  local host="$1"
  if [[ -z "${host}" || "${host}" == "0.0.0.0" || "${host}" == "::" ]]; then
    echo "127.0.0.1"
    return
  fi
  echo "${host}"
}

function sync_network_urls() {
  local app_origin_host api_origin_host
  app_origin_host="$(normalize_origin_host "${APP_HOST}")"
  api_origin_host="$(normalize_origin_host "${API_HOST}")"
  write_env_value "WEB_ORIGIN" "http://${app_origin_host}:${APP_PORT}"
  write_env_value "NEXT_PUBLIC_API_BASE_URL" "http://${api_origin_host}:${API_PORT}"
}

function read_env_value() {
  local key="$1"
  ensure_env
  local line
  line="$(grep -E "^${key}=" "${ENV_FILE}" | tail -n 1 || true)"
  local value="${line#*=}"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  echo "${value}"
}

function command_doctor() {
  ensure_env
  echo "检查运行环境..."
  echo "mode: $(runtime_mode)"
  command -v python3 >/dev/null 2>&1 && echo "python3: ok" || echo "python3: missing"
  command -v node >/dev/null 2>&1 && echo "node: ok" || echo "node: missing"
  command -v npm >/dev/null 2>&1 && echo "npm: ok" || echo "npm: missing"
  command -v ffmpeg >/dev/null 2>&1 && echo "ffmpeg: ok" || echo "ffmpeg: missing"
  if is_macos; then
    command -v brew >/dev/null 2>&1 && echo "brew: ok" || echo "brew: missing"
  fi
  if [[ -d "${VENV_DIR}" ]]; then
    echo "venv: ok"
  else
    echo "venv: missing"
  fi
  if [[ -d "${ROOT_DIR}/node_modules" ]]; then
    echo "node_modules: ok"
  else
    echo "node_modules: missing"
  fi
  if [[ -f "${ROOT_DIR}/apps/web/.next/BUILD_ID" ]]; then
    echo "web_build: ok"
  else
    echo "web_build: missing"
  fi
  if [[ -s "${ENV_FILE}" ]]; then
    echo ".env: ok"
  else
    echo ".env: missing"
  fi
  if [[ -n "$(read_env_value "DASHSCOPE_API_KEY")" ]]; then
    echo "DASHSCOPE_API_KEY: set"
  else
    echo "DASHSCOPE_API_KEY: missing"
  fi
  if [[ -n "$(read_env_value "APP_ADMIN_PASSWORD")" ]]; then
    echo "APP_ADMIN_PASSWORD: set"
  else
    echo "APP_ADMIN_PASSWORD: missing"
  fi
  if (cd "${ROOT_DIR}" && npx playwright --version >/dev/null 2>&1); then
    echo "playwright: ok"
  else
    echo "playwright: missing"
  fi
  if has_systemd; then
    echo "systemd: ok"
  else
    echo "systemd: unsupported"
  fi
  if is_ubuntu; then
    echo "os: ubuntu"
  elif is_macos; then
    echo "os: macos"
  else
    echo "os: other"
  fi
}

function set_named_config_value() {
  local key="$1"
  local current_value
  current_value="$(read_env_value "${key}")"
  printf '当前 %s=%s\n' "${key}" "${current_value:-<未设置>}"
  printf '请输入新的值: '
  local new_value
  read -r new_value
  if ! confirm_action "确认写入 ${key} 吗？"; then
    echo "已取消写入。"
    return 0
  fi
  write_env_value "${key}" "${new_value}"
  if [[ "${key}" == "APP_HOST" || "${key}" == "APP_PORT" || "${key}" == "API_HOST" || "${key}" == "API_PORT" ]]; then
    sync_network_urls
    echo "已同步 WEB_ORIGIN 和 NEXT_PUBLIC_API_BASE_URL。"
  fi
  echo "已更新 ${key}。"
}

function config_menu() {
  while true; do
    refresh_runtime_config
    printf '\n---------------- 配置管理 ----------------\n'
    printf '1. 查看当前配置摘要\n'
    printf '2. 修改 APP_HOST\n'
    printf '3. 修改 APP_PORT\n'
    printf '4. 修改 API_HOST\n'
    printf '5. 修改 API_PORT\n'
    printf '6. 修改 APP_DOMAIN\n'
    printf '7. 修改 APP_ADMIN_PASSWORD\n'
    printf '8. 修改 DASHSCOPE_API_KEY\n'
    printf '9. 读取任意配置键\n'
    printf '10. 写入任意配置键\n'
    printf '11. 返回主菜单\n'
    printf '请选择操作 [1-11]: '
    local choice
    read -r choice
    case "${choice}" in
      1) print_current_config; pause_screen ;;
      2) set_named_config_value "APP_HOST"; pause_screen ;;
      3) set_named_config_value "APP_PORT"; pause_screen ;;
      4) set_named_config_value "API_HOST"; pause_screen ;;
      5) set_named_config_value "API_PORT"; pause_screen ;;
      6) set_named_config_value "APP_DOMAIN"; pause_screen ;;
      7) set_named_config_value "APP_ADMIN_PASSWORD"; pause_screen ;;
      8) set_named_config_value "DASHSCOPE_API_KEY"; pause_screen ;;
      9)
        printf '请输入要读取的 KEY: '
        local read_key
        read -r read_key
        printf '%s=%s\n' "${read_key}" "$(read_env_value "${read_key}")"
        pause_screen
        ;;
      10)
        printf '请输入要写入的 KEY: '
        local write_key
        read -r write_key
        printf '请输入要写入的 VALUE: '
        local write_value
        read -r write_value
        if confirm_action "确认写入 ${write_key} 吗？"; then
          write_env_value "${write_key}" "${write_value}"
          echo "已更新 ${write_key}。"
        else
          echo "已取消写入。"
        fi
        pause_screen
        ;;
      11) return 0 ;;
      *) echo "无效选择，请重新输入。"; pause_screen ;;
    esac
  done
}

function main_menu() {
  while true; do
    refresh_runtime_config
    print_header
    printf '1. 环境检查\n'
    printf '2. 安装部署\n'
    printf '3. 启动服务（选择开发/生产模式）\n'
    printf '4. 停止生产服务\n'
    printf '5. 重启生产服务\n'
    printf '6. 查看生产状态\n'
    printf '7. 查看生产状态(JSON)\n'
    printf '8. 查看生产日志\n'
    printf '9. 更新项目\n'
    printf '10. 重建前端\n'
    printf '11. 配置管理\n'
    printf '12. 退出\n'
    printf '请选择操作 [1-12]: '
    local choice
    read -r choice
    case "${choice}" in
      1) run_action_with_pause command_doctor ;;
      2) run_action_with_pause command_install ;;
      3) start_menu ;;
      4) run_action_with_pause command_stop ;;
      5) run_action_with_pause command_restart ;;
      6) run_action_with_pause command_status_text ;;
      7) run_action_with_pause command_status_json ;;
      8) run_action_with_pause command_logs ;;
      9) run_action_with_pause command_update ;;
      10) run_action_with_pause command_rebuild_web ;;
      11) config_menu ;;
      12) echo "已退出。"; return 0 ;;
      *) echo "无效选择，请重新输入。"; pause_screen ;;
    esac
  done
}

refresh_runtime_config
ensure_interactive_tty

if [[ $# -gt 0 ]]; then
  echo "当前为菜单模式，已忽略传入参数：$*"
fi

main_menu
