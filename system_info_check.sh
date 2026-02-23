#!/bin/bash

################################################################################
# KONFIGURATION
################################################################################

# SSH Verbindungsdaten
SSH_USER="admin_onboard"
SSH_HOST="10.10.66.166"
SSH_PORT=22

# Optional: Passwort (leer lassen für key-basierte Auth)
SSH_PASSWORD=""

################################################################################
# SCRIPT - NICHT BEARBEITEN
################################################################################

echo "========================================"
echo "Remote System Info Check"
echo "========================================"
echo "Ziel: ${SSH_USER}@${SSH_HOST}:${SSH_PORT}"
echo "========================================"
echo ""

# SSH-Befehl vorbereiten
if [ -n "$SSH_PASSWORD" ]; then
    # Mit Passwort (benötigt sshpass)
    SSH_CMD="sshpass -p '$SSH_PASSWORD' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -p $SSH_PORT ${SSH_USER}@${SSH_HOST}"
else
    # Ohne Passwort (Key-basiert)
    SSH_CMD="ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -p $SSH_PORT ${SSH_USER}@${SSH_HOST}"
fi

# Remote-Script das auf dem Zielsystem ausgeführt wird
read -r -d '' REMOTE_SCRIPT << 'EOF'
#!/bin/bash

echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    SYSTEM INFORMATION                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Hostname
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🖥️  HOSTNAME"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
hostname
echo ""

# Betriebssystem
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🐧 BETRIEBSSYSTEM"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "Distribution:  $NAME"
    echo "Version:       $VERSION"
    echo "Codename:      $VERSION_CODENAME"
else
    uname -a
fi
echo ""

# CPU Information
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚙️  CPU"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f /proc/cpuinfo ]; then
    CPU_MODEL=$(grep "model name" /proc/cpuinfo | head -1 | cut -d: -f2 | xargs)
    CPU_CORES=$(grep -c "^processor" /proc/cpuinfo)
    echo "Modell:        $CPU_MODEL"
    echo "Kerne:         $CPU_CORES"
else
    echo "CPU Info nicht verfügbar"
fi
echo ""

# Temperatur
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌡️  TEMPERATUR (ALLE SENSOREN)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if command -v sensors &> /dev/null; then
    sensors
    echo ""
fi

if [ -d /sys/class/hwmon ]; then
    for hw in /sys/class/hwmon/hwmon*; do
        [ -d "$hw" ] || continue
        HW_NAME="$(cat "$hw/name" 2>/dev/null)"
        for temp in "$hw"/temp*_input; do
            [ -f "$temp" ] || continue
            RAW_TEMP=$(cat "$temp")
            LABEL_FILE="${temp%_input}_label"
            if [ -f "$LABEL_FILE" ]; then
                LABEL=$(cat "$LABEL_FILE")
            else
                LABEL=$(basename "$temp" | sed 's/_input//')
            fi
            if [ -n "$RAW_TEMP" ]; then
                TEMP_C=$(awk "BEGIN {printf \"%.1f\", $RAW_TEMP/1000}")
                if [ -n "$HW_NAME" ]; then
                    echo "$HW_NAME/$LABEL: ${TEMP_C}°C"
                else
                    echo "$LABEL: ${TEMP_C}°C"
                fi
            fi
        done
    done
fi

if [ -d /sys/class/thermal ]; then
    for zone in /sys/class/thermal/thermal_zone*; do
        [ -f "$zone/temp" ] || continue
        RAW_TEMP=$(cat "$zone/temp")
        if [ -f "$zone/type" ]; then
            ZONE_TYPE=$(cat "$zone/type")
        else
            ZONE_TYPE="thermal"
        fi
        if [ -n "$RAW_TEMP" ]; then
            TEMP_C=$(awk "BEGIN {printf \"%.1f\", $RAW_TEMP/1000}")
            echo "$ZONE_TYPE: ${TEMP_C}°C"
        fi
    done
fi

if ! command -v sensors &> /dev/null && [ ! -d /sys/class/hwmon ] && [ ! -d /sys/class/thermal ]; then
    echo "Temperatur nicht verfügbar"
fi
echo ""

# CPU Last pro Kern
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧠 CPU KERN LAST (AKTUELL)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if command -v mpstat &> /dev/null; then
    mpstat -P ALL 1 1 | awk 'NR>3 && $2 ~ /^[0-9]+$/ {printf "Core %s: %.1f%%\n", $2, 100-$NF}'
else
    awk -v interval=1 '
        BEGIN {for (i=0;i<999;i++) prev_total[i]=prev_idle[i]=0}
        NR==FNR && $1 ~ /^cpu[0-9]+$/ {
            cpu=substr($1,4)
            total=$2+$3+$4+$5+$6+$7+$8
            idle=$5
            prev_total[cpu]=total
            prev_idle[cpu]=idle
            next
        }
        NR!=FNR && $1 ~ /^cpu[0-9]+$/ {
            cpu=substr($1,4)
            total=$2+$3+$4+$5+$6+$7+$8
            idle=$5
            dt=total-prev_total[cpu]
            di=idle-prev_idle[cpu]
            if (dt>0) {
                usage=(dt-di)*100/dt
                printf "Core %s: %.1f%%\n", cpu, usage
            }
        }
    ' /proc/stat <(sleep 1; cat /proc/stat)
fi
echo ""

# RAM Information
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💾 ARBEITSSPEICHER (RAM)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f /proc/meminfo ]; then
    TOTAL_RAM=$(grep "MemTotal:" /proc/meminfo | awk '{printf "%.2f GB", $2/1024/1024}')
    FREE_RAM=$(grep "MemAvailable:" /proc/meminfo | awk '{printf "%.2f GB", $2/1024/1024}')
    USED_RAM=$(free -h | awk 'NR==2 {print $3}')
    USED_PCT=$(free | awk 'NR==2 {printf "%.1f%%", $3*100/$2}')
    echo "Gesamt:        $TOTAL_RAM"
    echo "Belegt:        $USED_RAM ($USED_PCT)"
    echo "Verfügbar:     $FREE_RAM"
else
    free -h
fi
echo ""

# Festplatten Information
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💿 FESTPLATTEN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
df -h / | awk 'NR==1 {print "Partition      Größe    Belegt   Frei     Nutzung  Mount"} 
               NR>1 {printf "%-14s %-8s %-8s %-8s %-8s %s\n", $1, $2, $3, $4, $5, $6}'
echo ""

# Weitere Mountpoints falls vorhanden
if df -h | grep -v "^/dev/loop" | grep "^/dev/" | tail -n +2 | wc -l | grep -q -v "^1$"; then
    echo "Weitere Partitionen:"
    df -h | grep -v "^/dev/loop" | grep "^/dev/" | tail -n +2 | awk '{printf "%-14s %-8s %-8s %-8s %-8s %s\n", $1, $2, $3, $4, $5, $6}'
    echo ""
fi

# Uptime
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⏱️  UPTIME & LOAD"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
uptime
echo ""

# Wichtige Packages Check
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 WICHTIGE PACKAGES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Liste wichtiger Packages
PACKAGES=("python3" "git" "curl" "wget" "vim" "gcc" "make" "docker" "ssh")

for pkg in "${PACKAGES[@]}"; do
    if command -v "$pkg" &> /dev/null; then
        VERSION=$(command -v "$pkg" | xargs dpkg -S 2>/dev/null | cut -d: -f1 | xargs dpkg -l 2>/dev/null | tail -1 | awk '{print $3}' 2>/dev/null)
        if [ -z "$VERSION" ]; then
            # Fallback: Version direkt vom Command
            case "$pkg" in
                python3)
                    VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
                    ;;
                git)
                    VERSION=$(git --version 2>&1 | cut -d' ' -f3)
                    ;;
                docker)
                    VERSION=$(docker --version 2>&1 | cut -d' ' -f3 | tr -d ',')
                    ;;
                *)
                    VERSION="installiert"
                    ;;
            esac
        fi
        printf "%-15s ✅ %s\n" "$pkg" "$VERSION"
    else
        printf "%-15s ❌ nicht installiert\n" "$pkg"
    fi
done
echo ""

# Netzwerk
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 NETZWERK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "IP Adressen:"
ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v "127.0.0.1" | while read ip; do
    echo "  → $ip"
done
echo ""

echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    CHECK ABGESCHLOSSEN                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
EOF

# Remote-Script ausführen
eval $SSH_CMD "bash -s" << EOF
$REMOTE_SCRIPT
EOF

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Verbindung erfolgreich getrennt"
else
    echo "❌ Fehler beim Verbinden (Exit Code: $EXIT_CODE)"
fi
