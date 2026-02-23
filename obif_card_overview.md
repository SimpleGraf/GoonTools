========================================
Remote System Info Check
========================================
Ziel: admin_onboard@10.42.0.67:22
========================================

admin_onboard@10.42.0.67's password: 
╔════════════════════════════════════════════════════════════╗
║                    SYSTEM INFORMATION                      ║
╚════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🖥️  HOSTNAME
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
localhost

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🐧 BETRIEBSSYSTEM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Distribution:  Ubuntu
Version:       22.04.1 LTS (Jammy Jellyfish)
Codename:      jammy

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚙️  CPU
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Modell:        Intel(R) Atom(TM) Processor E3950 @ 1.60GHz
Kerne:         4

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💾 ARBEITSSPEICHER (RAM)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Gesamt:        7.61 GB
Belegt:        193Mi
Verfügbar:     7.19 GB

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💿 FESTPLATTEN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Partition      Größe    Belegt   Frei     Nutzung  Mount
/dev/mapper/obif-root 4.9G     1.9G     2.8G     40%      /

Weitere Partitionen:
/dev/mmcblk1p2 284M     75M      187M     29%      /boot
/dev/mmcblk1p1 63M      5.0M     58M      8%       /boot/efi
/dev/mapper/obif-appl 104M     452K     95M      1%       /opt
/dev/mapper/obif-conf 104M     80K      95M      1%       /etc/opt
/dev/mapper/obif-data 4.5G     112M     4.2G     3%       /var
/dev/sda1      464G     112G     352G     25%      /mnt/iocard

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️  UPTIME & LOAD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 13:51:49 up 3 min,  1 user,  load average: 0.13, 0.12, 0.05

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 WICHTIGE PACKAGES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
python3         ✅ 3.10.6-1~22.04.1
git             ❌ nicht installiert
curl            ❌ nicht installiert
wget            ✅ 1.21.2-2ubuntu1
vim             ✅ 1.4.8+dfsg-3build1
gcc             ❌ nicht installiert
make            ❌ nicht installiert
docker          ❌ nicht installiert
ssh             ✅ 1:8.9p1-3ubuntu0.1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌐 NETZWERK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IP Adressen:
  → 10.42.0.67

╔════════════════════════════════════════════════════════════╗
║                    CHECK ABGESCHLOSSEN                     ║
╚════════════════════════════════════════════════════════════╝

✅ Verbindung erfolgreich getrennt

========================================
Karte (IO-Speicher) und Mount
========================================
Gefundene Karte: /dev/sda1 (ext3)
Mountpunkt: /mnt/iocard

Einmalig mounten:
sudo mkdir -p /mnt/iocard
sudo mount /dev/sda1 /mnt/iocard

Dauerhaft einhaengen (fstab):
UUID=94d51f90-eb55-4049-8025-9d563db56029  /mnt/iocard  ext3  defaults  0  2

========================================
SimplePositioning Installation (Dateien + Pfade)
========================================
Zielpfad der App:
/home/simpo/simplepositioning

Benutzer:
- simpo (kein sudo)
- hitachi (admin)

Dateien, die vorhanden sind:
/home/hitachi/deploy/
  - simplePositioning (Start-Skript)
  - simplePositioning.service (systemd Service)
  - simplepositioning-0.5.4-py3-none-any.whl
  - simplepositioning-0.5.4.tar.gz

Dateien nach /home/simpo/simplepositioning kopieren:
sudo -u simpo mkdir -p /home/simpo/simplepositioning
sudo cp /home/hitachi/deploy/simplePositioning /home/simpo/simplepositioning/
sudo cp /home/hitachi/deploy/simplePositioning.service /home/simpo/simplepositioning/
sudo cp /home/hitachi/deploy/simplepositioning-0.5.4-py3-none-any.whl /home/simpo/simplepositioning/
sudo chown -R simpo:simpo /home/simpo/simplepositioning

Virtuelle Umgebung und Paket installieren:
sudo -u simpo python3 -m venv /home/simpo/simplepositioning/.venv
sudo -u simpo /home/simpo/simplepositioning/.venv/bin/pip install /home/simpo/simplepositioning/simplepositioning-0.5.4-py3-none-any.whl

Service installieren (als root):
sudo cp /home/simpo/simplepositioning/simplePositioning.service /etc/systemd/system/simplePositioning.service
sudo systemctl daemon-reload
sudo systemctl enable simplePositioning.service
sudo systemctl start simplePositioning.service

hitachi@localhost:~$ df -h
Filesystem             Size  Used Avail Use% Mounted on
tmpfs                  780M  1.1M  779M   1% /run
/dev/mapper/obif-root  4.9G  1.9G  2.8G  40% /
tmpfs                  3.9G     0  3.9G   0% /dev/shm
tmpfs                  5.0M     0  5.0M   0% /run/lock
tmpfs                  1.0G  4.0K  1.0G   1% /tmp
/dev/mmcblk1p2         284M   75M  187M  29% /boot
/dev/mmcblk1p1          63M  5.0M   58M   8% /boot/efi
/dev/mapper/obif-appl  104M  452K   95M   1% /opt
/dev/mapper/obif-conf  104M   80K   95M   1% /etc/opt
/dev/mapper/obif-data  4.5G  112M  4.2G   3% /var
/dev/sda1              464G  112G  352G  25% /mnt/iocard
tmpfs                  780M     0  780M   0% /run/user/1001


hitachi@localhost:~$ ls -all
total 48
drwxr-xr-x 5 hitachi hitachi  4096 Feb 10 17:46 .
drwxr-xr-x 4 root    root     4096 Feb 10 11:47 ..
-rw------- 1 hitachi hitachi 10168 Feb 10 21:00 .bash_history
-rw-r--r-- 1 hitachi hitachi   220 Feb 10 11:41 .bash_logout
-rw-r--r-- 1 hitachi hitachi  3771 Feb 10 11:41 .bashrc
drwx------ 2 hitachi hitachi  4096 Feb 10 17:31 .cache
-rw-r--r-- 1 hitachi hitachi   807 Feb 10 11:41 .profile
-rw-r--r-- 1 hitachi hitachi     0 Feb 10 11:51 .sudo_as_admin_successful
-rw------- 1 hitachi hitachi   995 Feb 10 14:29 .viminfo
drwxrwxr-x 4 hitachi hitachi  4096 Feb 10 18:36 deploy
drwxrwxr-x 2 hitachi simpo    4096 Feb 10 17:46 venv-debs

hitachi@localhost:/home/simpo$ ls -all
total 40
drwxr-x--- 5 simpo simpo 4096 Feb 10 18:17 .
drwxr-xr-x 4 root  root  4096 Feb 10 11:47 ..
-rw------- 1 simpo simpo  691 Feb 10 21:00 .bash_history
-rw-r--r-- 1 simpo simpo  220 Feb 10 11:47 .bash_logout
-rw-r--r-- 1 simpo simpo 3771 Feb 10 11:47 .bashrc
drwx------ 2 simpo simpo 4096 Feb 10 17:05 .cache
-rw-r--r-- 1 simpo simpo  807 Feb 10 11:47 .profile
drwx------ 2 simpo simpo 4096 Feb 10 11:49 .ssh
-rw------- 1 simpo simpo  952 Feb 10 18:17 .viminfo
drwxrwxr-x 4 simpo simpo 4096 Feb 10 18:47 simplepositioning