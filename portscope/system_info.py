from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any

from .logger import log_event


class ModuleReadError(RuntimeError):
    pass


@dataclass
class PortSnapshot:
    usb_items: list[dict[str, str]]
    net_items: list[dict[str, str]]
    disk_items: list[dict[str, str]]
    connected_items: list[dict[str, str]]
    notes: list[str]
    alerts: list[str]
    benchmark_targets: list[dict[str, str]]
    summary_cards: list[dict[str, str]]
    module_errors: list[str]
    module_statuses: list[dict[str, str]]


def _run_powershell_json(script: str) -> list[dict[str, Any]]:
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    raw = (completed.stdout or "").strip()
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "Fallo la consulta de PowerShell.").strip()
        log_event(
            "powershell_failed",
            returncode=completed.returncode,
            stderr=message[:400],
            script=script[:160],
        )
        raise ModuleReadError(message or "Fallo la consulta de PowerShell.")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        log_event("powershell_invalid_json", script=script[:160], raw=raw[:400])
        raise ModuleReadError("Windows devolvio una respuesta invalida para esta consulta.")
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        return [parsed]
    return []


def _normalize(value: Any, fallback: str = "No disponible") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def format_bytes(value: Any) -> str:
    try:
        size = float(value)
    except (TypeError, ValueError):
        return "No disponible"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return "No disponible"


def infer_usb_speed(name: str, instance_id: str) -> tuple[str, str]:
    text = f"{name} {instance_id}".lower()
    if "usb4" in text:
        return "Hasta 40 Gbps", "Alta"
    if "usb 3.2" in text or "usb32" in text:
        return "Hasta 20 Gbps", "Alta"
    if "usb 3.1" in text or "usb31" in text or "3.10" in text:
        return "Hasta 10 Gbps", "Alta"
    if "usb 3.0" in text or "root_hub30" in text or "usb30" in text:
        return "Hasta 5 Gbps", "Media"
    if "usb 2.0" in text or "usb20" in text:
        return "Hasta 480 Mbps", "Basica"
    if "usb 1." in text:
        return "Hasta 12 Mbps", "Basica"
    return "Sin dato claro", "Desconocida"


def classify_usb(name: str, instance_id: str) -> str:
    lowered = f"{name} {instance_id}".lower()
    if "controller" in lowered or instance_id.startswith("PCI\\"):
        return "Controlador"
    if "root hub" in lowered or "hub" in lowered:
        return "Hub"
    return "Dispositivo"


def _usb_energy_hint(name: str, category: str) -> str:
    lowered = name.lower()
    if category in {"Controlador", "Hub"}:
        return "Lectura no disponible; este elemento solo expone control del puerto"
    if "type-c" in lowered or "usb-c" in lowered:
        return "USB-C detectado; potencia real solo visible con hardware o driver compatible"
    if "composite" in lowered:
        return "Depende del dispositivo; Windows no muestra voltaje o amperaje real"
    return "No medible desde Windows; requiere medidor USB o software del fabricante"


def _friendly_device_type(name: str, manufacturer: str, instance_id: str) -> str:
    text = f"{name} {manufacturer} {instance_id}".lower()
    if "logitech" in text or "mouse" in text:
        return "Mouse USB"
    if "keyboard" in text or "teclado" in text:
        return "Teclado USB"
    if "hub" in text:
        return "Hub USB"
    if "storage" in text or "flash" in text or "kingston" in text or "sandisk" in text:
        return "Almacenamiento USB"
    if "phone" in text or "iphone" in text or "android" in text:
        return "Telefono"
    if "ethernet" in text or "network" in text:
        return "Adaptador de red USB"
    if "composite" in text:
        return "Dispositivo USB"
    return "Dispositivo conectado"


def collect_usb_items() -> list[dict[str, str]]:
    script = r"""
$items = Get-PnpDevice -PresentOnly |
    Where-Object { $_.Class -eq 'USB' } |
    Select-Object Status, FriendlyName, InstanceId, Class, Manufacturer
$items | ConvertTo-Json -Depth 3
"""
    rows = _run_powershell_json(script)
    result = []
    for row in rows:
        name = _normalize(row.get("FriendlyName"), "USB sin nombre")
        instance_id = _normalize(row.get("InstanceId"))
        category = classify_usb(name, instance_id)
        speed, tier = infer_usb_speed(name, instance_id)
        result.append(
            {
                "categoria": category,
                "nombre": name,
                "estado": _normalize(row.get("Status")),
                "fabricante": _normalize(row.get("Manufacturer")),
                "instancia": instance_id,
                "velocidad": speed,
                "nivel": tier,
                "energia": _usb_energy_hint(name, category),
            }
        )
    return sorted(result, key=lambda item: (item["categoria"], item["nombre"]))


def collect_connected_items(usb_items: list[dict[str, str]]) -> list[dict[str, str]]:
    connected = []
    for item in usb_items:
        if item["categoria"] != "Dispositivo":
            continue
        name = item["nombre"]
        manufacturer = item["fabricante"]
        connected.append(
            {
                "id": item["instancia"],
                "nombre": name,
                "tipo": _friendly_device_type(name, manufacturer, item["instancia"]),
                "fabricante": manufacturer,
                "estado": item["estado"],
                "velocidad": item["velocidad"],
            }
        )
    return sorted(connected, key=lambda item: item["nombre"])


def _network_kind(description: str) -> str:
    lowered = description.lower()
    if "virtual" in lowered or "vmware" in lowered:
        return "Virtual"
    if "wi-fi" in lowered or "wireless" in lowered:
        return "Wi-Fi"
    if "ethernet" in lowered or "gbe" in lowered:
        return "Ethernet"
    if "bluetooth" in lowered:
        return "Bluetooth"
    return "Red"


def _connection_state(value: Any) -> str:
    normalized = _normalize(value)
    return {
        "0": "Unknown",
        "1": "Connected",
        "2": "Disconnected",
    }.get(normalized, normalized)


def _drive_type_label(value: Any) -> str:
    normalized = _normalize(value)
    return {
        "0": "Unknown",
        "2": "Removible",
        "3": "Fijo",
        "4": "Red",
        "5": "CD/DVD",
        "6": "RAM",
        "Fixed": "Fijo",
    }.get(normalized, normalized)


def collect_net_items() -> list[dict[str, str]]:
    script = r"""
$items = Get-NetAdapter |
    Select-Object Name, InterfaceDescription, Status, LinkSpeed, MacAddress, MediaConnectionState
$items | ConvertTo-Json -Depth 3
"""
    rows = _run_powershell_json(script)
    result = []
    for row in rows:
        description = _normalize(row.get("InterfaceDescription"))
        result.append(
            {
                "nombre": _normalize(row.get("Name")),
                "descripcion": description,
                "tipo": _network_kind(description),
                "estado": _normalize(row.get("Status")),
                "conexion": _connection_state(row.get("MediaConnectionState")),
                "velocidad": _normalize(row.get("LinkSpeed")),
                "mac": _normalize(row.get("MacAddress")),
            }
        )
    return sorted(result, key=lambda item: item["nombre"])


def collect_disk_items() -> list[dict[str, str]]:
    script = r"""
$volumes = Get-Volume | Select-Object DriveLetter, FileSystemLabel, DriveType, HealthStatus, SizeRemaining, Size
$volumes | ConvertTo-Json -Depth 3
"""
    rows = _run_powershell_json(script)
    result = []
    for row in rows:
        drive_letter = _normalize(row.get("DriveLetter"), "Sin letra")
        target = drive_letter if drive_letter == "Sin letra" else f"{drive_letter}:\\"
        result.append(
            {
                "unidad": target,
                "etiqueta": _normalize(row.get("FileSystemLabel"), "Sin etiqueta"),
                "tipo": _drive_type_label(row.get("DriveType")),
                "salud": _normalize(row.get("HealthStatus")),
                "libre": format_bytes(row.get("SizeRemaining")),
                "tamano": format_bytes(row.get("Size")),
                "benchmark_target": target,
            }
        )
    return sorted(result, key=lambda item: item["unidad"])


def build_benchmark_targets(disk_items: list[dict[str, str]]) -> list[dict[str, str]]:
    targets = []
    for item in disk_items:
        target = item.get("benchmark_target", "")
        if not target.endswith("\\"):
            continue
        label_parts = [
            item["unidad"],
            item["tipo"],
            item["etiqueta"],
            f"Libre: {item['libre']}",
        ]
        targets.append(
            {
                "label": "  |  ".join(label_parts),
                "path": target,
            }
        )
    return targets


def build_alerts(usb_items: list[dict[str, str]], net_items: list[dict[str, str]], disk_items: list[dict[str, str]]) -> list[str]:
    alerts = []
    if not any(item["categoria"] == "Dispositivo" for item in usb_items):
        alerts.append("No hay dispositivos USB de usuario detectados en este momento; solo controladores o hubs.")
    if any(item["velocidad"] == "Hasta 480 Mbps" for item in usb_items):
        alerts.append("Hay elementos USB identificados como clase USB 2.0; podrian limitar transferencias modernas.")
    connected_nets = [item for item in net_items if item["conexion"].lower() == "connected"]
    if not connected_nets:
        alerts.append("No hay adaptadores de red activos en estado conectado.")
    elif not any(item["tipo"] == "Ethernet" and item["conexion"].lower() == "connected" for item in net_items):
        alerts.append("No hay enlace Ethernet fisico activo; las pruebas de red dependerian de Wi-Fi o adaptadores virtuales.")
    if not any(item["unidad"].endswith("\\") for item in disk_items):
        alerts.append("No se detectaron unidades con letra listas para benchmark automatico.")
    return alerts[:5]


def build_summary_cards(usb_items: list[dict[str, str]], net_items: list[dict[str, str]], disk_items: list[dict[str, str]]) -> list[dict[str, str]]:
    usb_devices = sum(1 for item in usb_items if item["categoria"] == "Dispositivo")
    active_networks = sum(1 for item in net_items if item["conexion"].lower() == "connected")
    benchmark_ready = sum(1 for item in disk_items if item["unidad"].endswith("\\"))
    return [
        {"title": "USB visibles", "value": str(len(usb_items)), "caption": f"{usb_devices} de usuario"},
        {"title": "Red activa", "value": str(active_networks), "caption": "adaptadores conectados"},
        {"title": "Unidades listas", "value": str(benchmark_ready), "caption": "candidatas para test"},
    ]


def build_module_statuses(
    usb_items: list[dict[str, str]],
    net_items: list[dict[str, str]],
    disk_items: list[dict[str, str]],
    module_errors: list[str],
) -> list[dict[str, str]]:
    error_map = {
        "usb": next((item for item in module_errors if item.lower().startswith("usb ")), ""),
        "red": next((item for item in module_errors if item.lower().startswith("red ")), ""),
        "unidades": next((item for item in module_errors if item.lower().startswith("unidades ")), ""),
    }
    return [
        {
            "modulo": "USB",
            "estado": "Error" if error_map["usb"] else "OK",
            "detalle": error_map["usb"] or f"{len(usb_items)} elemento(s) leidos",
        },
        {
            "modulo": "Red",
            "estado": "Error" if error_map["red"] else "OK",
            "detalle": error_map["red"] or f"{len(net_items)} adaptador(es) leidos",
        },
        {
            "modulo": "Unidades",
            "estado": "Error" if error_map["unidades"] else "OK",
            "detalle": error_map["unidades"] or f"{len(disk_items)} unidad(es) leidas",
        },
    ]


def collect_snapshot() -> PortSnapshot:
    module_errors: list[str] = []

    try:
        usb_items = collect_usb_items()
    except Exception as exc:
        usb_items = []
        module_errors.append(f"USB no se pudo leer: {exc}")
        log_event("snapshot_module_failed", module="usb", error=str(exc))

    try:
        net_items = collect_net_items()
    except Exception as exc:
        net_items = []
        module_errors.append(f"Red no se pudo leer: {exc}")
        log_event("snapshot_module_failed", module="net", error=str(exc))

    try:
        disk_items = collect_disk_items()
    except Exception as exc:
        disk_items = []
        module_errors.append(f"Unidades no se pudo leer: {exc}")
        log_event("snapshot_module_failed", module="disk", error=str(exc))

    connected_items = collect_connected_items(usb_items)
    notes = [
        "La velocidad USB puede ser teorica o inferida desde el controlador o hub detectado.",
        "Windows no suele exponer voltaje, amperaje o potencia real de carga en puertos USB comunes.",
        "Para energia real normalmente hace falta hardware USB tester o drivers del fabricante.",
        "Los benchmarks de PortScope miden lectura y escritura reales en la ruta seleccionada.",
    ]
    alerts = build_alerts(usb_items, net_items, disk_items)
    if module_errors:
        alerts = module_errors + alerts
    return PortSnapshot(
        usb_items=usb_items,
        net_items=net_items,
        disk_items=disk_items,
        connected_items=connected_items,
        notes=notes,
        alerts=alerts,
        benchmark_targets=build_benchmark_targets(disk_items),
        summary_cards=build_summary_cards(usb_items, net_items, disk_items),
        module_errors=module_errors,
        module_statuses=build_module_statuses(usb_items, net_items, disk_items, module_errors),
    )
