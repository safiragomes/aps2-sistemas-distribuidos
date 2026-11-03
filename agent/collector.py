# Reaproveitado da aps 1

# Coleta das métricas de CPU e memória RAM

import psutil


def collect_memory():
    mem_info = psutil.virtual_memory()
    mb_divisor = 1024 * 1024

    return {
        "total_mb": int(mem_info.total / mb_divisor),
        "used_mb": int(mem_info.used / mb_divisor),
        "free_mb": int(mem_info.free / mb_divisor)
    }


def collect_cpu():
    # Mede todos os núcleos no mesmo intervalo
    cores_cpu = psutil.cpu_percent(interval=0.1, percpu=True)

    # Calcula a média geral a partir dos núcleos coletados
    if cores_cpu:
        overall_cpu = round(sum(cores_cpu) / len(cores_cpu), 1)
    else:
        overall_cpu = 0.0

    return {
        "overall": overall_cpu,
        "cores": cores_cpu
    }


def collect_metrics():
    return {
        "type": "METRICS",
        "cpu": collect_cpu(),
        "memory": collect_memory()
    }