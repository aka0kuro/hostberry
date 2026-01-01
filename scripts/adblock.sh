#!/bin/bash

# Configuración de idioma
# Idioma por defecto: español. Se puede sobrescribir con --language=XX
LANGUAGE="es"
SYS_LANG="${LC_ALL:-${LC_MESSAGES:-${LANG}}}"
if [[ "$SYS_LANG" == en* ]]; then
    LANGUAGE="en"
fi

# Textos
if [ "$LANGUAGE" = "en" ]; then
    MSG_DOWNLOADING="Downloading"
    MSG_DOWNLOAD_SUCCESS="Successfully downloaded"
    MSG_DOWNLOAD_FAIL="Failed to download"
    MSG_REALTIME_STATS="=== Realtime Blocking Statistics ==="
    MSG_LAST_10="Last 10 blocked domains:"
    MSG_TOTAL_BLOCKED="Total domains blocked in last hour:"
    MSG_NO_STATS="No realtime statistics available"
    MSG_PROCESSED="Processed"
    MSG_UNIQUE_DOMAINS="unique domains and created"
    MSG_BLOCKING_RULES="blocking rules"
    MSG_NO_LISTS="No lists specified"
    MSG_DISABLED="AdBlock disabled"
    MSG_USAGE="Usage: $0 --lists <list1 list2 ...> or --disable or --realtime"
else
    MSG_DOWNLOADING="Descargando"
    MSG_DOWNLOAD_SUCCESS="Descargado exitosamente"
    MSG_DOWNLOAD_FAIL="Fallo al descargar"
    MSG_REALTIME_STATS="=== Estadísticas de Bloqueo en Tiempo Real ==="
    MSG_LAST_10="Últimos 10 dominios bloqueados:"
    MSG_TOTAL_BLOCKED="Total de dominios bloqueados en la última hora:"
    MSG_NO_STATS="No hay estadísticas en tiempo real disponibles"
    MSG_PROCESSED="Procesados"
    MSG_UNIQUE_DOMAINS="dominios únicos y creadas"
    MSG_BLOCKING_RULES="reglas de bloqueo"
    MSG_NO_LISTS="No se especificaron listas"
    MSG_DISABLED="AdBlock deshabilitado"
    MSG_USAGE="Uso: $0 --lists <lista1 lista2 ...> o --disable o --realtime"
fi

# Configuración
ADBLOCK_DIR="/etc/hostberry/adblock"
HOSTS_FILE="/etc/hosts"
TEMP_DIR="/opt/hostberry/logs"
STATS_FILE="$ADBLOCK_DIR/stats.json"
LOG_FILE="$ADBLOCK_DIR/blocked.log"
REALTIME_LOG="$ADBLOCK_DIR/realtime.log"

# URLs de las listas
EASYLIST_URL="https://easylist.to/easylist/easylist.txt"
EASYPRIVACY_URL="https://easylist.to/easylist/easyprivacy.txt"
FANBOY_URL="https://easylist.to/easylist/fanboy-annoyance.txt"
MALWARE_URL="https://mirror.cedia.org.ec/malwaredomains/domains.txt"
SOCIAL_URL="https://easylist.to/easylist/fanboy-social.txt"

# Nuevas listas adicionales
KADHOSTS_URL="https://raw.githubusercontent.com/PolishFiltersTeam/KADhosts/master/KADhosts.txt"
ADOBE_TRACKERS_URL="https://raw.githubusercontent.com/FadeMind/hosts.extras/master/add.2o7Net/hosts"
FIRSTPARTY_TRACKERS_URL="https://hostfiles.frogeye.fr/firstparty-trackers-hosts.txt"
STEVENBLACK_URL="https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts"
WINDOWS_SPY_URL="https://raw.githubusercontent.com/crazy-max/WindowsSpyBlocker/master/data/hosts/spy.txt"

# Crear solo directorio temporal, el de configuración debe existir
mkdir -p "$TEMP_DIR"

# Función para registrar un dominio bloqueado en tiempo real
log_realtime() {
    local domain=$1
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] Blocked: $domain" | tee -a "$REALTIME_LOG" > /dev/null
    # Mantener solo las últimas 1000 entradas
    tail -n 1000 "$REALTIME_LOG" | tee "$REALTIME_LOG.tmp" > /dev/null && mv "$REALTIME_LOG.tmp" "$REALTIME_LOG"
}

# Función para mostrar estadísticas en tiempo real
show_realtime_stats() {
    if [ -f "$REALTIME_LOG" ]; then
        echo "$MSG_REALTIME_STATS"
        echo "$MSG_LAST_10"
        sudo tail -n 10 "$REALTIME_LOG"
        echo -e "\n$MSG_TOTAL_BLOCKED"
        sudo grep "$(date -d '1 hour ago' '+%Y-%m-%d %H')" "$REALTIME_LOG" | wc -l
    else
        echo "$MSG_NO_STATS"
    fi
}

# Función para descargar y procesar una lista
download_list() {
    local url=$1
    local name=$2
    echo "$MSG_DOWNLOADING $name..."
    curl -s "$url" > "$TEMP_DIR/$name"
    if [ $? -eq 0 ]; then
        echo "$MSG_DOWNLOAD_SUCCESS $name"
        return 0
    else
        echo "$MSG_DOWNLOAD_FAIL $name"
        return 1
    fi
}

# Función para extraer dominio de una regla
extract_domain() {
    local rule=$1
    # Eliminar el prefijo "||" y el sufijo "^"
    domain=${rule#"||"}
    domain=${domain%"^"}
    # Verificar que es un dominio válido
    if [[ $domain =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        echo "$domain"
    fi
}

# Función para procesar las listas
process_lists() {
    local lists=$1
    local domains=0
    local rules=0
    
    # Limpiar archivos temporales
    > "$TEMP_DIR/combined.txt"
    > "$TEMP_DIR/domains.txt"
    
    # Procesar cada lista seleccionada
    for list in $lists; do
        case $list in
            "easylist")
                download_list "$EASYLIST_URL" "easylist.txt"
                grep -E '^\|\|[^\/]+\^$' "$TEMP_DIR/easylist.txt" > "$TEMP_DIR/easylist_filtered.txt"
                while IFS= read -r line; do
                    domain=$(extract_domain "$line")
                    if [ ! -z "$domain" ]; then
                        echo "$domain" >> "$TEMP_DIR/domains.txt"
                        log_realtime "$domain"
                    fi
                done < "$TEMP_DIR/easylist_filtered.txt"
                ;;
            "easyprivacy")
                download_list "$EASYPRIVACY_URL" "easyprivacy.txt"
                grep -E '^\|\|[^\/]+\^$' "$TEMP_DIR/easyprivacy.txt" > "$TEMP_DIR/easyprivacy_filtered.txt"
                while IFS= read -r line; do
                    domain=$(extract_domain "$line")
                    if [ ! -z "$domain" ]; then
                        echo "$domain" >> "$TEMP_DIR/domains.txt"
                        log_realtime "$domain"
                    fi
                done < "$TEMP_DIR/easyprivacy_filtered.txt"
                ;;
            "fanboy")
                download_list "$FANBOY_URL" "fanboy.txt"
                grep -E '^\|\|[^\/]+\^$' "$TEMP_DIR/fanboy.txt" > "$TEMP_DIR/fanboy_filtered.txt"
                while IFS= read -r line; do
                    domain=$(extract_domain "$line")
                    if [ ! -z "$domain" ]; then
                        echo "$domain" >> "$TEMP_DIR/domains.txt"
                        log_realtime "$domain"
                    fi
                done < "$TEMP_DIR/fanboy_filtered.txt"
                ;;
            "malware")
                download_list "$MALWARE_URL" "malware.txt"
                grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' "$TEMP_DIR/malware.txt" >> "$TEMP_DIR/domains.txt"
                ;;
            "social")
                download_list "$SOCIAL_URL" "social.txt"
                grep -E '^\|\|[^\/]+\^$' "$TEMP_DIR/social.txt" > "$TEMP_DIR/social_filtered.txt"
                while IFS= read -r line; do
                    domain=$(extract_domain "$line")
                    if [ ! -z "$domain" ]; then
                        echo "$domain" >> "$TEMP_DIR/domains.txt"
                        log_realtime "$domain"
                    fi
                done < "$TEMP_DIR/social_filtered.txt"
                ;;
            "kadhosts")
                download_list "$KADHOSTS_URL" "kadhosts.txt"
                grep -E '^0\.0\.0\.0' "$TEMP_DIR/kadhosts.txt" | awk '{print $2}' >> "$TEMP_DIR/domains.txt"
                ;;
            "adobe")
                download_list "$ADOBE_TRACKERS_URL" "adobe.txt"
                grep -E '^0\.0\.0\.0' "$TEMP_DIR/adobe.txt" | awk '{print $2}' >> "$TEMP_DIR/domains.txt"
                ;;
            "firstparty")
                download_list "$FIRSTPARTY_TRACKERS_URL" "firstparty.txt"
                grep -E '^0\.0\.0\.0' "$TEMP_DIR/firstparty.txt" | awk '{print $2}' >> "$TEMP_DIR/domains.txt"
                ;;
            "stevenblack")
                download_list "$STEVENBLACK_URL" "stevenblack.txt"
                grep -E '^0\.0\.0\.0' "$TEMP_DIR/stevenblack.txt" | awk '{print $2}' >> "$TEMP_DIR/domains.txt"
                ;;
            "windows")
                download_list "$WINDOWS_SPY_URL" "windows.txt"
                grep -E '^0\.0\.0\.0' "$TEMP_DIR/windows.txt" | awk '{print $2}' >> "$TEMP_DIR/domains.txt"
                ;;
        esac
    done
    
    # Eliminar duplicados y contar dominios únicos
    sort -u "$TEMP_DIR/domains.txt" > "$TEMP_DIR/unique_domains.txt"
    domains=$(wc -l < "$TEMP_DIR/unique_domains.txt")
    
    # Preparar el archivo hosts
    > "$TEMP_DIR/combined.txt"
    while IFS= read -r domain; do
        if [ ! -z "$domain" ]; then
            echo "0.0.0.0 $domain" >> "$TEMP_DIR/combined.txt"
            echo "0.0.0.0 www.$domain" >> "$TEMP_DIR/combined.txt"
        fi
    done < "$TEMP_DIR/unique_domains.txt"
    
    # Contar reglas totales
    rules=$(wc -l < "$TEMP_DIR/combined.txt")
    
    # Guardar estadísticas
    echo "{\"domains_blocked\": $domains, \"rules_active\": $rules}" | sudo tee "$STATS_FILE" > /dev/null
    
    # Actualizar hosts file
    if [ -f "$HOSTS_FILE" ]; then
        # Hacer backup del archivo hosts
        sudo cp "$HOSTS_FILE" "$HOSTS_FILE.bak"
        
        # Eliminar bloqueos anteriores
        sudo sed -i '/# AdBlock Start/,/# AdBlock End/d' "$HOSTS_FILE"
        
        # Añadir nuevos bloqueos
        echo "# AdBlock Start" | sudo tee -a "$HOSTS_FILE" > /dev/null
        cat "$TEMP_DIR/combined.txt" | sudo tee -a "$HOSTS_FILE" > /dev/null
        echo "# AdBlock End" | sudo tee -a "$HOSTS_FILE" > /dev/null
        
        # Limpiar caché DNS
        if command -v systemd-resolve >/dev/null 2>&1; then
            sudo systemd-resolve --flush-caches
        elif command -v service >/dev/null 2>&1; then
            sudo service nscd restart 2>/dev/null || true
        fi
    fi
    
    # Guardar timestamp de actualización
    date +"%Y-%m-%d %H:%M:%S" | sudo tee "$ADBLOCK_DIR/last_updated" > /dev/null
    
    echo "Processed $domains unique domains and created $rules blocking rules"
    show_realtime_stats
}

# Manejar argumentos
case "$1" in
    "--lists")
        if [ -z "$2" ]; then
            echo "No lists specified"
            exit 1
        fi
        process_lists "$2"
        ;;
    "--disable")
        if [ -f "$HOSTS_FILE" ]; then
            sudo sed -i '/# AdBlock Start/,/# AdBlock End/d' "$HOSTS_FILE"
            echo "AdBlock disabled"
            # Limpiar caché DNS
            if command -v systemd-resolve >/dev/null 2>&1; then
                sudo systemd-resolve --flush-caches
            elif command -v service >/dev/null 2>&1; then
                sudo service nscd restart 2>/dev/null || true
            fi
        fi
        ;;
    "--realtime")
        show_realtime_stats
        ;;
    *)
        echo "Usage: $0 --lists <list1 list2 ...> or --disable or --realtime"
        exit 1
        ;;
esac

# Limpiar
rm -rf "$TEMP_DIR"

exit 0
