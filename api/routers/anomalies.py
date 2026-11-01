from fastapi import APIRouter, HTTPException, Query

from api.services.anomaly_service import (
    detect_anomalies,
    get_anomaly_summary
)

router = APIRouter()


@router.get("")
def list_anomalies(
    severity: str | None = Query(default=None),
    anomaly_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0)
):
    anomalies = detect_anomalies()

    if severity:
        anomalies = [
            item for item in anomalies
            if item["severity"] == severity.upper()
        ]

    if anomaly_type:
        anomalies = [
            item for item in anomalies
            if item["anomaly_type"] == anomaly_type.upper()
        ]

    total = len(anomalies)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "anomalies": anomalies[offset:offset + limit]
    }


@router.get("/summary")
def anomaly_summary():
    anomalies = detect_anomalies()

    return get_anomaly_summary(anomalies)


@router.get("/{anomaly_id}")
def get_anomaly(anomaly_id: str):
    anomalies = detect_anomalies()

    for anomaly in anomalies:
        if anomaly["anomaly_id"] == anomaly_id:
            return anomaly

    raise HTTPException(
        status_code=404,
        detail="Anomaly not found"
    )