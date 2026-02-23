#!/bin/bash

################################################################################
# KONFIGURATION
################################################################################

# Netzwerk-Präfix (z.B. "10.10.66" für 10.10.66.0/24)
NETWORK_PREFIX="10.42.0"

# Start- und End-IP (letztes Oktet)
START_IP=1
END_IP=254

# Ping Timeout in Sekunden
PING_TIMEOUT=1

# Anzahl der Ping-Versuche
PING_COUNT=1

# Maximale Anzahl paralleler Prozesse
MAX_PARALLEL=50

################################################################################
# SCRIPT - NICHT BEARBEITEN
################################################################################

echo "========================================"
echo "Netzwerk Scanner"
echo "========================================"
echo "Netzwerk: ${NETWORK_PREFIX}.${START_IP}-${END_IP}"
echo "Scanning gestartet um $(date +"%H:%M:%S")"
echo "========================================"
echo ""

# Temporäre Datei für Ergebnisse
TEMP_FILE=$(mktemp)

# Cleanup bei Script-Beendigung
trap "rm -f $TEMP_FILE" EXIT

# Funktion zum Pingen einer IP
ping_ip() {
    local ip=$1
    if ping -c $PING_COUNT -W $PING_TIMEOUT $ip &> /dev/null; then
        echo "$ip" >> $TEMP_FILE
    fi
}

# Export der Funktion für parallel execution
export -f ping_ip
export PING_COUNT
export PING_TIMEOUT
export TEMP_FILE

# Zähler für laufende Prozesse
running=0

# Loop durch alle IPs
for i in $(seq $START_IP $END_IP); do
    ip="${NETWORK_PREFIX}.${i}"
    
    # Ping im Hintergrund starten
    ping_ip "$ip" &
    
    ((running++))
    
    # Warten wenn maximale Anzahl paralleler Prozesse erreicht
    if [ $running -ge $MAX_PARALLEL ]; then
        wait -n
        ((running--))
    fi
done

# Auf alle verbleibenden Prozesse warten
wait

echo ""
echo "========================================"
echo "Scan abgeschlossen um $(date +"%H:%M:%S")"
echo "========================================"
echo ""

# Ergebnisse sortieren und anzeigen
if [ -s $TEMP_FILE ]; then
    echo "Erreichbare Hosts:"
    echo "-------------------"
    sort -t . -k 4 -n $TEMP_FILE
    echo ""
    echo "Anzahl erreichbarer Hosts: $(wc -l < $TEMP_FILE)"
else
    echo "Keine erreichbaren Hosts gefunden."
fi

echo ""
