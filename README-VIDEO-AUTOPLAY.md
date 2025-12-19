# 🎬 QUIC File Transfer - Video Autoplay

## ✨ ¿Qué hace ahora?

Cuando recibas un video a través de QUIC:

1. **Se guarda automáticamente** en tu carpeta de descargas (`~/Descargas` o `~/Downloads`)
2. **Se abre automáticamente** en pantalla completa de tu host usando tu reproductor predeterminado
3. **Sin hacer nada manualmente** - es totalmente automático

---

## 🚀 Cómo usar

### Linux / macOS
```bash
./run-docker.sh
```

### Windows
```bat
run-docker.bat
```

**Eso es todo.** El script hará:
- ✅ Detectar tu carpeta de descargas automáticamente
- ✅ Iniciar el servidor QUIC en el contenedor
- ✅ Iniciar el monitor de videos en background
- ✅ Los videos se abrirán automáticamente en pantalla completa

---

## 📋 Flujo de Video

```
Video enviado desde otra máquina
    ↓
Servidor QUIC recibe el archivo
    ↓
Se guarda en ~/Descargas (o ~/Downloads)
    ↓
Monitor de videos lo detecta
    ↓
Abre automáticamente en pantalla completa
(con tu reproductor predeterminado)
```

---

## 🔧 Componentes

| Componente | Qué hace |
|-----------|----------|
| `run-docker.sh` | Inicia Docker + monitor (Linux/macOS) |
| `run-docker.bat` | Inicia Docker + monitor (Windows) |
| `video-monitor.sh` | Monitorea carpeta de descargas (Linux/macOS) |
| `video-monitor.bat` | Monitorea carpeta de descargas (Windows) |
| Docker Container | Servidor QUIC + Flask web |

---

## 📹 Reproductores soportados

El script intenta usar (en orden de preferencia):
1. **MPV** - reproductor recomendado para fullscreen
2. **VLC** - alternativa popular
3. **Reproductor predeterminado del sistema** - cualquiera que tengas configurado

---

## 🔒 Carpetas soportadas

El sistema detecta automáticamente:
- ✅ `~/Descargas` (español)
- ✅ `~/Downloads` (inglés)
- ✅ Crea la carpeta si no existe

---

## 📊 Monitoreo

Para ver qué está pasando:

**Linux/macOS:**
```bash
tail -f /tmp/video-monitor.log
```

**Windows:**
La ventana del monitor estará abierta mostrando los eventos

---

## ✅ Verificación

Después de ejecutar el script, deberías ver:
```
✓ Carpeta de descargas detectada: /home/usuario/Descargas
✓ Containers started successfully
✓ Monitor de videos activo (PID: XXXXX)
  Los videos se abrirán automáticamente en pantalla completa
✅ Sistema listo. Abre http://localhost:5000 para enviar videos
```

---

## ❓ Preguntas frecuentes

**P: ¿Qué pasa si no tengo reproductor instalado?**
A: Se intentará abrir con el reproductor predeterminado del sistema. Si no hay ninguno, el video se guardará pero no se abrirá automáticamente. Puedes abrirlo manualmente desde tu explorador de archivos.

**P: ¿Puedo cambiar el reproductor?**
A: Edita `video-monitor.sh` (Linux) o `video-monitor.bat` (Windows) y reemplaza el comando `open_video()` con tu reproductor preferido.

**P: ¿Se detiene el monitor si reinicio?**
A: No, mientras tengas `./run-docker.sh` ejecutándose, el monitor seguirá activo en background.

---

## 🛑 Para detener todo

```bash
# Detener Docker
docker compose -f templates/quic-file-transfer/docker-compose.yml down

# El monitor se detendrá automáticamente
```

---

**Estado:** ✅ Funcionando | **Última actualización:** 18 Dic 2025
