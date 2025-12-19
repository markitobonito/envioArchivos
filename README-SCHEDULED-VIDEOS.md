# 📺 Sistema de Programación de Videos

## ¿Qué es?

Ahora cuando envías un **video**, tienes 3 opciones:

1. **▶ Reproducir Ahora** - El video se abre en pantalla completa apenas llega (comportamiento anterior)
2. **⏰ Programar Reproducción** - Especifica hora y días para que se reproduzca automáticamente
3. **🤐 Solo Descargar** - El video se descarga en silencio, sin abrir

**Nota:** Estas opciones solo aparecen si el archivo es un video. Para otros archivos se envían normalmente.

---

## Cómo usar

### Opción 1: Reproducir Ahora ▶

1. Selecciona un video
2. Se muestra la sección "Programación de Video"
3. Selecciona "▶ Reproducir Ahora"
4. Envía el archivo
5. El video se abre automáticamente en pantalla completa cuando llega

### Opción 2: Programar Reproducción ⏰

1. Selecciona un video
2. Selecciona "⏰ Programar Reproducción"
3. Aparece un formulario con:
   - **Hora de Reproducción**: Selecciona la hora (ej: 14:30)
   - **Días de la Semana**: Marca los días cuando debe reproducirse (ej: Lunes, Miércoles, Viernes)
4. Envía el archivo
5. El video se abrirá **automáticamente a la hora especificada SOLO en los días seleccionados**

**Ejemplo:**
- Video: "Presentación.mp4"
- Hora: 09:00
- Días: Lunes, Martes, Miércoles
- Resultado: Se abrirá en pantalla completa a las 9:00 AM los lunes, martes y miércoles

### Opción 3: Solo Descargar 🤐

1. Selecciona un video
2. Selecciona "🤐 Solo Descargar"
3. Envía el archivo
4. El video se descarga silenciosamente sin abrirse

---

## Archivos importantes

Cuando programas un video, el sistema crea:
- **Video**: `WhatsApp Video 2025-12-18 at 4.53.56 PM.mp4`
- **Programación**: `WhatsApp Video 2025-12-18 at 4.53.56 PM.mp4.schedule.json`

El archivo `.schedule.json` contiene:
```json
{
  "filename": "WhatsApp Video 2025-12-18 at 4.53.56 PM.mp4",
  "time": "14:30",
  "days": ["monday", "wednesday", "friday"],
  "created_at": "1766102993"
}
```

---

## Cómo funciona

1. **Emisor envía video con programación**
   - El sistema crea un archivo `.schedule.json` en el servidor
   - Este archivo viaja junto con el video

2. **Receptor recibe video**
   - El video se guarda en `~/Descargas`
   - El monitor busca el archivo `.schedule.json`
   - Si existe, verifica hora y día actual
   - Si coinciden, abre el video automáticamente

3. **Monitor ejecuta cada 2 segundos**
   - Revisa cambios en la carpeta de descargas
   - Compara hora actual con programación
   - Abre videos cuando es su hora

---

## Casos de uso

### 1. Recordatorio de reunión
- Hora: 09:00
- Días: Todos los días hábiles (Lunes-Viernes)
- Video de introducción se abre automáticamente

### 2. Evento especial
- Hora: 20:00
- Días: Viernes y Sábado
- Video de entretenimiento se abre automáticamente

### 3. Transmisión silenciosa
- Selecciona "Solo Descargar"
- Descarga archivos para ver después sin interrupciones

---

## Limitaciones y consideraciones

- **Exactitud de hora**: El video se abre si la hora actual coincide EXACTAMENTE (HH:MM)
- **Zona horaria**: Se usa la zona horaria del receptor
- **Revisar cada 2 segundos**: Es lo suficientemente rápido para no perder el horario
- **Reproducción única por día**: Se reproduce una sola vez por día en cada hora programada

---

## Troubleshooting

**P: El video no se abre a la hora programada**
- Verifica que la hora esté correcta
- Verifica que hayas seleccionado el día correcto
- Asegúrate que el monitor está corriendo: `ps aux | grep video-monitor`

**P: ¿Puedo cambiar la hora después de enviar?**
- Sí, edita manualmente el archivo `.schedule.json` en la carpeta de descargas
- Guarda los cambios y el monitor lo detectará

**P: ¿El video se descarga mientras espera la hora?**
- Sí, se descarga inmediatamente pero NO se abre hasta la hora programada

---

**Estado:** ✅ Funcional | **Última actualización:** 18 Dic 2025
