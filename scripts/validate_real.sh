#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${HOSTBERRY_BASE_URL:-http://localhost:8000}"
USER="${HOSTBERRY_USER:-}"
PASS="${HOSTBERRY_PASS:-}"

if [[ -z "${USER}" || -z "${PASS}" ]]; then
  echo "[ERROR] Debes definir HOSTBERRY_USER y HOSTBERRY_PASS (credenciales reales)."
  echo "Ejemplo:"
  echo "  HOSTBERRY_USER=admin HOSTBERRY_PASS=admin HOSTBERRY_BASE_URL=http://localhost:8000 ./scripts/validate_real.sh"
  exit 2
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

echo "[INFO] Login contra ${BASE_URL} ..."
login_json="$(curl -sS -X POST "${BASE_URL}/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  --data "{\"username\":\"${USER}\",\"password\":\"${PASS}\"}")"

token="$(python3 - <<'PY'
import json,sys
data=json.loads(sys.stdin.read() or "{}")
print(data.get("access_token",""))
PY
<<<"$login_json")"

if [[ -z "${token}" ]]; then
  echo "[ERROR] No se pudo obtener access_token. Respuesta:"
  echo "$login_json"
  exit 1
fi

echo "[OK] Token obtenido. Validando HTML (rutas web) ..."

cookie_header="Cookie: access_token=${token}"

web_paths=(
  "/"
  "/dashboard"
  "/settings"
  "/network"
  "/wifi"
  "/wifi-scan"
  "/vpn"
  "/wireguard"
  "/adblock"
  "/hostapd"
  "/profile"
  "/system"
  "/monitoring"
  "/update"
)

fail=0

for p in "${web_paths[@]}"; do
  code="$(curl -sS -o /dev/null -w '%{http_code}' -H "${cookie_header}" "${BASE_URL}${p}")"
  if [[ "${code}" != "200" && "${code}" != "302" ]]; then
    echo "[FAIL] WEB ${p} -> HTTP ${code}"
    fail=1
  else
    echo "[OK]   WEB ${p} -> HTTP ${code}"
  fi
done

echo "[INFO] Validando API con datos reales ..."

api_paths=(
  "/api/v1/auth/me"
  "/api/v1/system/info"
  "/api/v1/system/stats"
  "/api/v1/system/logs?level=all&limit=5&offset=0"
  "/api/v1/network/status"
  "/api/v1/network/interfaces"
  "/api/v1/wifi/scan"
  "/api/v1/vpn/status"
  "/api/v1/wireguard/status"
  "/api/v1/adblock/status"
)

auth_header="Authorization: Bearer ${token}"

for p in "${api_paths[@]}"; do
  code="$(curl -sS -o "${tmpdir}/out.json" -w '%{http_code}' -H "${auth_header}" "${BASE_URL}${p}" || true)"
  if [[ "${code}" != "200" ]]; then
    echo "[WARN] API ${p} -> HTTP ${code}"
    echo "       Body (primeras 300 chars):"
    head -c 300 "${tmpdir}/out.json" || true
    echo ""
    # No marcamos fail automático porque algunos endpoints pueden requerir permisos/hardware (p.ej. wifi_scan)
  else
    echo "[OK]   API ${p} -> HTTP ${code}"
  fi
done

if [[ "${fail}" -ne 0 ]]; then
  echo "[ERROR] Validación WEB falló en alguna ruta."
  exit 1
fi

echo "[OK] Validación WEB completa. Revisa warnings de API si aparecen."

