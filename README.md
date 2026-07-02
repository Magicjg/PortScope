# PortScope

Aplicacion de escritorio para Windows orientada a diagnosticar puertos, enlaces y rendimiento real de transferencia.

## Que hace

- Detecta inventario USB, red, unidades y dispositivos conectados ahora mismo
- Muestra estado por modulo para distinguir entre lectura correcta y fallo parcial
- Ejecuta benchmark real de lectura y escritura en una ruta elegida
- Guarda historial de benchmarks y lo exporta a CSV
- Exporta inventario completo a JSON o a un paquete CSV por secciones
- Incluye modo claro y modo nocturno

## Funciones incluidas

- Barra superior de informacion con resumen tecnico fuera de la vista principal
- Modo claro y modo nocturno con mejor contraste visual
- Paleta renovada para tablas, tarjetas, botones y paneles
- Recordatorio de tema, carpeta usada y configuracion del benchmark
- Filtros de busqueda para USB, red y unidades
- Inventario USB con fabricante, categoria, velocidad estimada y pista de energia
- Inventario de red con tipo de adaptador, estado y velocidad negociada
- Inventario de unidades con letra, salud, espacio libre y tamano
- Estado de modulos USB, red y unidades para detectar fallos parciales
- Benchmark con varias pasadas para lectura y escritura real
- Historial persistente de pruebas y exportacion a CSV
- Exportacion de inventario a JSON o paquete CSV

## Limitaciones honestas

- Windows no expone de forma uniforme el voltaje y amperaje real de carga para todos los puertos USB
- La velocidad USB mostrada puede ser teorica o inferida segun lo que reporta el sistema
- Para potencia electrica real conviene complementar con hardware USB tester

## Requisitos

- Windows 10 u 11
- Python 3.11+ para ejecutar desde codigo
- No depende de librerias de runtime externas; usa Tkinter y utilidades del propio sistema

## Ejecutar desde codigo

```powershell
python .\app.py
```

## Crear el EXE de release

Instala dependencias de build:

```powershell
pip install -r .\requirements.txt
```

Genera el ejecutable y el ZIP de release:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_release.ps1
```

Salida esperada:

- `release\PortScope-0.5.1-win64\PortScope.exe`
- `release\PortScope-0.5.1-win64.zip`

## Tests

```powershell
python -m unittest discover -s .\tests -v
```

## Estructura del proyecto

- `app.py`: entrada principal de la app
- `portscope/ui.py`: interfaz Tkinter y flujo principal
- `portscope/system_info.py`: lectura de USB, red, unidades y snapshot general
- `portscope/benchmark.py`: benchmark real de lectura y escritura
- `portscope/history.py`: historial y preferencias
- `portscope/logger.py`: logs locales
- `portscope/exporters.py`: exportacion de inventario
- `tests/`: pruebas automatizadas
- `scripts/build_release.ps1`: build del ejecutable
- `assets/portscope.ico`: icono del ejecutable y de la app

## Logs y datos locales

PortScope guarda informacion local en:

- `C:\Users\<tu_usuario>\.portscope\history.json`
- `C:\Users\<tu_usuario>\.portscope\settings.json`
- `C:\Users\<tu_usuario>\.portscope\portscope.log`

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Revisa [LICENSE](./LICENSE).
