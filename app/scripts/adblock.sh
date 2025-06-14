#!/bin/bash

# Configuración
ADBLOCK_DIR="/etc/hostberry/adblock"
HOSTS_FILE="/etc/hosts"
TEMP_DIR="/tmp/adblock"
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

# Crear directorios si no existen
sudo mkdir -p "$ADBLOCK_DIR"
sudo mkdir -p "$TEMP_DIR"

# Función para registrar un dominio bloqueado en tiempo real
log_realtime() {
    local domain=$1
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    # Asegurarse de que el archivo existe
    if [ ! -f "$REALTIME_LOG" ]; then
        sudo touch "$REALTIME_LOG"
        sudo chmod 644 "$REALTIME_LOG"
    fi
    echo "[$timestamp] Blocked: $domain" | sudo tee -a "$REALTIME_LOG" > /dev/null
    # Mantener solo las últimas 1000 entradas
    if [ -f "$REALTIME_LOG" ]; then
        sudo tail -n 1000 "$REALTIME_LOG" > "$REALTIME_LOG.tmp" 2>/dev/null
        if [ -f "$REALTIME_LOG.tmp" ]; then
            sudo mv "$REALTIME_LOG.tmp" "$REALTIME_LOG" 2>/dev/null
        fi
    fi
}

# Función para mostrar estadísticas en tiempo real
show_realtime_stats() {
    if [ -f "$REALTIME_LOG" ]; then
        echo "=== Realtime Blocking Statistics ==="
        echo "Last 10 blocked domains:"
        sudo tail -n 10 "$REALTIME_LOG"
        echo -e "\nTotal domains blocked in last hour:"
        sudo grep "$(date -d '1 hour ago' '+%Y-%m-%d %H')" "$REALTIME_LOG" | wc -l
    else
        echo "No realtime statistics available"
    fi
}

# Función para descargar y procesar una lista
download_list() {
    local url=$1
    local name=$2
    echo "Downloading $name..."
    curl -s "$url" > "$TEMP_DIR/$name"
    if [ $? -eq 0 ]; then
        echo "Successfully downloaded $name"
        return 0
    else
        echo "Failed to download $name"
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
    sudo rm -rf "$TEMP_DIR"
    sudo mkdir -p "$TEMP_DIR"
    sudo chmod 755 "$TEMP_DIR"
    
    > "$TEMP_DIR/combined.txt"
    > "$TEMP_DIR/domains.txt"
    
    echo "Processing lists: $lists"
    
    # Procesar cada lista seleccionada
    for list in $lists; do
        echo "Processing list: $list"
        case $list in
            "easylist")
                if download_list "$EASYLIST_URL" "easylist.txt"; then
                    echo "Filtering easylist..."
                    grep -E '^\|\|[^\/]+\^$' "$TEMP_DIR/easylist.txt" > "$TEMP_DIR/easylist_filtered.txt"
                    while IFS= read -r line; do
                        domain=$(extract_domain "$line")
                        if [ ! -z "$domain" ]; then
                            echo "$domain" >> "$TEMP_DIR/domains.txt"
                            log_realtime "$domain"
                        fi
                    done < "$TEMP_DIR/easylist_filtered.txt"
                fi
                ;;
            "easyprivacy")
                if download_list "$EASYPRIVACY_URL" "easyprivacy.txt"; then
                    echo "Filtering easyprivacy..."
                    grep -E '^\|\|[^\/]+\^$' "$TEMP_DIR/easyprivacy.txt" > "$TEMP_DIR/easyprivacy_filtered.txt"
                    while IFS= read -r line; do
                        domain=$(extract_domain "$line")
                        if [ ! -z "$domain" ]; then
                            echo "$domain" >> "$TEMP_DIR/domains.txt"
                            log_realtime "$domain"
                        fi
                    done < "$TEMP_DIR/easyprivacy_filtered.txt"
                fi
                ;;
            "fanboy")
                if download_list "$FANBOY_URL" "fanboy.txt"; then
                    echo "Filtering fanboy..."
                    grep -E '^\|\|[^\/]+\^$' "$TEMP_DIR/fanboy.txt" > "$TEMP_DIR/fanboy_filtered.txt"
                    while IFS= read -r line; do
                        domain=$(extract_domain "$line")
                        if [ ! -z "$domain" ]; then
                            echo "$domain" >> "$TEMP_DIR/domains.txt"
                            log_realtime "$domain"
                        fi
                    done < "$TEMP_DIR/fanboy_filtered.txt"
                fi
                ;;
            "malware")
                if download_list "$MALWARE_URL" "malware.txt"; then
                    echo "Filtering malware..."
                    grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' "$TEMP_DIR/malware.txt" >> "$TEMP_DIR/domains.txt"
                fi
                ;;
            "social")
                if download_list "$SOCIAL_URL" "social.txt"; then
                    echo "Filtering social..."
                    grep -E '^\|\|[^\/]+\^$' "$TEMP_DIR/social.txt" > "$TEMP_DIR/social_filtered.txt"
                    while IFS= read -r line; do
                        domain=$(extract_domain "$line")
                        if [ ! -z "$domain" ]; then
                            echo "$domain" >> "$TEMP_DIR/domains.txt"
                            log_realtime "$domain"
                        fi
                    done < "$TEMP_DIR/social_filtered.txt"
                fi
                ;;
            "kadhosts")
                if download_list "$KADHOSTS_URL" "kadhosts.txt"; then
                    echo "Filtering kadhosts..."
                    grep -E '^0\.0\.0\.0' "$TEMP_DIR/kadhosts.txt" | awk '{print $2}' >> "$TEMP_DIR/domains.txt"
                fi
                ;;
            "adobe")
                if download_list "$ADOBE_TRACKERS_URL" "adobe.txt"; then
                    echo "Filtering adobe..."
                    grep -E '^0\.0\.0\.0' "$TEMP_DIR/adobe.txt" | awk '{print $2}' >> "$TEMP_DIR/domains.txt"
                fi
                ;;
            "firstparty")
                if download_list "$FIRSTPARTY_TRACKERS_URL" "firstparty.txt"; then
                    echo "Filtering firstparty..."
                    grep -E '^0\.0\.0\.0' "$TEMP_DIR/firstparty.txt" | awk '{print $2}' >> "$TEMP_DIR/domains.txt"
                fi
                ;;
            "stevenblack")
                if download_list "$STEVENBLACK_URL" "stevenblack.txt"; then
                    echo "Filtering stevenblack..."
                    grep -E '^0\.0\.0\.0' "$TEMP_DIR/stevenblack.txt" | awk '{print $2}' >> "$TEMP_DIR/domains.txt"
                fi
                ;;
            "windows")
                if download_list "$WINDOWS_SPY_URL" "windows.txt"; then
                    echo "Filtering windows..."
                    grep -E '^0\.0\.0\.0' "$TEMP_DIR/windows.txt" | awk '{print $2}' >> "$TEMP_DIR/domains.txt"
                fi
                ;;
        esac
    done
    
    echo "Removing duplicates..."
    # Eliminar duplicados y contar dominios únicos
    sort -u "$TEMP_DIR/domains.txt" > "$TEMP_DIR/unique_domains.txt"
    domains=$(wc -l < "$TEMP_DIR/unique_domains.txt")
    
    echo "Preparing hosts file..."
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
    
    echo "Saving statistics..."
    # Guardar estadísticas
    echo "{\"domains_blocked\": $domains, \"rules_active\": $rules, \"lists_active\": $(echo $lists | wc -w)}" | sudo tee "$STATS_FILE" > /dev/null
    
    echo "Updating hosts file..."
    # Actualizar hosts file
    if [ -f "$HOSTS_FILE" ]; then
        # Hacer backup del archivo hosts
        sudo cp "$HOSTS_FILE" "$HOSTS_FILE.bak"
        
        # Eliminar bloqueos anteriores
        sudo sed -i '/# AdBlock Start/,/# AdBlock End/d' "$HOSTS_FILE"
        
        # Añadir nuevos bloqueos
        echo "# AdBlock Start" | sudo tee -a "$HOSTS_FILE" > /dev/null
        sudo cat "$TEMP_DIR/combined.txt" | sudo tee -a "$HOSTS_FILE" > /dev/null
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
