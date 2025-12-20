import platform
import socket
import subprocess

def show_native_notification(title, message, duration=5):
    system = platform.system()
    try:
        if system == "Darwin":
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script])
        elif system == "Windows":
            ps_script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$APP_ID = 'QuicFileTransfer'
$template = @"
<toast>
    <visual>
        <binding template=\"ToastText02\">
            <text id=\"1\">{title}</text>
            <text id=\"2\">{message}</text>
        </binding>
    </visual>
</toast>
"@
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($APP_ID).Show($toast)
"""
            subprocess.run(["powershell", "-Command", ps_script])
        elif system == "Linux":
            subprocess.run(["notify-send", "-u", "critical", "-t", str(duration * 1000), title, message])
    except Exception as e:
        print("Error mostrando notificación:", e)

def main():
    UDP_IP = "0.0.0.0"
    UDP_PORT = 9999
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"[+] Esperando mensajes en {UDP_IP}:{UDP_PORT} ... (Ctrl+C para salir)")
    while True:
        data, addr = sock.recvfrom(2048)
        if data.startswith(b"MSG:\0"):
            message = data[5:].decode("utf-8", errors="ignore")
            print(f"[ALERTA] Mensaje recibido de {addr}: {message}")
            show_native_notification("🚨 ALERTA URGENTE", message, 8)

if __name__ == "__main__":
    main()
