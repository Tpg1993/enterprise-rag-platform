"""Enterprise built-in tools providing safe mathematical calculation, SLA penalties,
system calendar oracles, and service catalog lookups.
"""

import ast
import datetime
import math
import operator
from typing import Any

# Allowed operators for AST safe math evaluation
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_MATH_FUNCS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "ceil": math.ceil,
    "floor": math.floor,
    "min": min,
    "max": max,
    "log": math.log,
}


def _eval_ast(node: ast.AST) -> float | int:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type in _OPERATORS:
            left = _eval_ast(node.left)
            right = _eval_ast(node.right)
            return _OPERATORS[op_type](left, right)
        raise ValueError(f"Unsupported binary operator: {op_type.__name__}")
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type in _OPERATORS:
            return _OPERATORS[op_type](_eval_ast(node.operand))
        raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        func_name = node.func.id
        if func_name in _MATH_FUNCS:
            args = [_eval_ast(arg) for arg in node.args]
            return _MATH_FUNCS[func_name](*args)
        raise ValueError(f"Unsupported function call: {func_name}")
    raise ValueError(f"Unsupported AST node expression: {type(node).__name__}")


def calculate(expression: str) -> dict[str, Any]:
    """Safely evaluates an arithmetic expression using AST parsing without eval()."""
    clean_expr = expression.strip()
    try:
        parsed = ast.parse(clean_expr, mode="eval")
        result = _eval_ast(parsed.body)
        return {
            "expression": clean_expr,
            "result": round(result, 6) if isinstance(result, float) else result,
            "formatted": f"{result:,.2f}" if isinstance(result, (int, float)) else str(result),
        }
    except Exception as e:
        raise ValueError(f"Invalid arithmetic expression '{clean_expr}': {e!s}")


def calculate_sla_penalty(
    downtime_hours: float,
    hourly_rate_usd: float = 1200.0,
    penalty_multiplier: float = 1.5,
) -> dict[str, Any]:
    """Calculates enterprise downtime credits and contractual liability penalties."""
    if downtime_hours < 0:
        raise ValueError("downtime_hours must be non-negative.")
    if hourly_rate_usd <= 0:
        raise ValueError("hourly_rate_usd must be positive.")

    base_cost = downtime_hours * hourly_rate_usd
    total_penalty = base_cost * penalty_multiplier

    if downtime_hours >= 4.0:
        severity = "CRITICAL"
    elif downtime_hours >= 1.0:
        severity = "HIGH"
    elif downtime_hours >= 0.25:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    return {
        "downtime_hours": downtime_hours,
        "hourly_rate_usd": hourly_rate_usd,
        "penalty_multiplier": penalty_multiplier,
        "base_loss_usd": round(base_cost, 2),
        "total_penalty_credit_usd": round(total_penalty, 2),
        "severity": severity,
        "summary": (
            f"Downtime of {downtime_hours}h incurred ${total_penalty:,.2f} penalty "
            f"(Severity: {severity}) based on multiplier {penalty_multiplier}x."
        ),
    }


def get_system_time(timezone: str = "UTC") -> dict[str, Any]:
    """Returns current system UTC datetime, quarter, and enterprise business day status."""
    now = datetime.datetime.now(datetime.UTC)
    is_weekend = now.weekday() >= 5
    quarter = (now.month - 1) // 3 + 1

    return {
        "timezone": "UTC",
        "iso_timestamp": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S UTC"),
        "day_of_week": now.strftime("%A"),
        "quarter": f"Q{quarter}",
        "is_business_day": not is_weekend,
    }


def query_service_catalog(service_name: str) -> dict[str, Any]:
    """Looks up architecture metadata, SLA targets, and tier for core platform services."""
    catalog = {
        "qdrant": {
            "name": "Qdrant Vector DB",
            "tier": "Tier-1 Mission Critical",
            "sla_target": "99.99%",
            "port": 6333,
            "owner": "Infrastructure Team",
            "status": "OPERATIONAL",
        },
        "neo4j": {
            "name": "Neo4j Graph Database",
            "tier": "Tier-1 Mission Critical",
            "sla_target": "99.95%",
            "port": 7687,
            "owner": "Data Platform Team",
            "status": "OPERATIONAL",
        },
        "fastapi": {
            "name": "FastAPI Core Gateway",
            "tier": "Tier-1 Mission Critical",
            "sla_target": "99.99%",
            "port": 8000,
            "owner": "Backend Services Team",
            "status": "OPERATIONAL",
        },
        "redis": {
            "name": "Redis Distributed Cache",
            "tier": "Tier-2 High Availability",
            "sla_target": "99.90%",
            "port": 6379,
            "owner": "SRE Team",
            "status": "OPERATIONAL",
        },
        "sarvam-105b": {
            "name": "Sarvam-105B LLM Provider",
            "tier": "Tier-1 Mission Critical",
            "sla_target": "99.95%",
            "owner": "AI Platform Team",
            "status": "OPERATIONAL",
        },
    }

    key = service_name.strip().lower()
    for s_key, data in catalog.items():
        if key in s_key or s_key in key:
            return data

    return {
        "service": service_name,
        "status": "UNKNOWN",
        "detail": f"Service '{service_name}' not listed in primary enterprise catalog.",
    }


def unit_converter(value: float, from_unit: str, to_unit: str) -> dict[str, Any]:
    """Converts digital storage units or time units."""
    from_u = from_unit.strip().lower()
    to_u = to_unit.strip().lower()

    # Byte storage ratios relative to bytes
    storage_ratios = {
        "b": 1.0,
        "byte": 1.0,
        "bytes": 1.0,
        "kb": 1024.0,
        "mb": 1024.0**2,
        "gb": 1024.0**3,
        "tb": 1024.0**4,
    }

    # Time ratios relative to seconds
    time_ratios = {
        "ms": 0.001,
        "s": 1.0,
        "sec": 1.0,
        "min": 60.0,
        "hr": 3600.0,
        "hour": 3600.0,
        "day": 86400.0,
    }

    if from_u in storage_ratios and to_u in storage_ratios:
        bytes_val = value * storage_ratios[from_u]
        converted = bytes_val / storage_ratios[to_u]
        return {
            "value": value,
            "from_unit": from_unit,
            "to_unit": to_unit,
            "result": round(converted, 4),
            "formatted": f"{converted:,.4f} {to_unit}",
        }

    if from_u in time_ratios and to_u in time_ratios:
        seconds_val = value * time_ratios[from_u]
        converted = seconds_val / time_ratios[to_u]
        return {
            "value": value,
            "from_unit": from_unit,
            "to_unit": to_unit,
            "result": round(converted, 4),
            "formatted": f"{converted:,.4f} {to_unit}",
        }

    raise ValueError(f"Incompatible unit conversion from '{from_unit}' to '{to_unit}'.")
