"""Google Routes API ile trafik duyarlı teslimat sıralama."""

import json
import logging
from itertools import permutations
from typing import List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from odoo import _, fields
from odoo.exceptions import UserError

from .teslimat_utils import prepare_maps_destination

_logger = logging.getLogger(__name__)

GOOGLE_ROUTE_MATRIX_URL = (
    "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
)
PARAM_API_KEY = "teslimat_planlama.google_maps_api_key"
PARAM_DEPOT = "teslimat_planlama.rota_baslangic_adres"
ROTA_SIRALANABILIR_DURUMLAR = ("hazir", "yolda")


def get_maps_route_config(env) -> dict:
    """Sistem parametrelerinden rota yapılandırmasını oku."""
    icp = env["ir.config_parameter"].sudo()
    return {
        "api_key": (icp.get_param(PARAM_API_KEY) or "").strip(),
        "depot": (icp.get_param(PARAM_DEPOT) or "").strip()
        or "İstanbul, Türkiye",
    }


def is_route_api_configured(env) -> bool:
    return bool(get_maps_route_config(env)["api_key"])


def _duration_to_seconds(duration: Optional[str]) -> Optional[int]:
    if not duration or not isinstance(duration, str):
        return None
    duration = duration.strip()
    if duration.endswith("s"):
        try:
            return int(duration[:-1])
        except ValueError:
            return None
    return None


def _fetch_travel_matrix(api_key: str, addresses: List[str]) -> List[List[Optional[int]]]:
    """NxN süre matrisi (saniye). addresses[0] depo/başlangıç."""
    n = len(addresses)
    if n == 0:
        return []

    payload = {
        "origins": [{"waypoint": {"address": addr}} for addr in addresses],
        "destinations": [{"waypoint": {"address": addr}} for addr in addresses],
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
    }
    request = Request(
        GOOGLE_ROUTE_MATRIX_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "originIndex,destinationIndex,duration,condition",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        _logger.error("Google Routes API HTTP %s: %s", exc.code, body[:500])
        raise UserError(
            _(
                "Google Routes API hatası (HTTP %(code)s).\n"
                "API anahtarı ve Routes API etkinliğini kontrol edin."
            )
            % {"code": exc.code}
        ) from exc
    except URLError as exc:
        _logger.error("Google Routes API bağlantı hatası: %s", exc)
        raise UserError(_("Google Routes API'ye bağlanılamadı.")) from exc

    try:
        elements = json.loads(raw)
    except json.JSONDecodeError as exc:
        _logger.error("Google Routes API geçersiz JSON: %s", raw[:500])
        raise UserError(_("Google Routes API beklenmeyen yanıt döndürdü.")) from exc

    matrix: List[List[Optional[int]]] = [[None] * n for _ in range(n)]
    if isinstance(elements, list):
        for element in elements:
            if element.get("condition") != "ROUTE_EXISTS":
                continue
            o_idx = element.get("originIndex")
            d_idx = element.get("destinationIndex")
            if o_idx is None or d_idx is None:
                continue
            if 0 <= o_idx < n and 0 <= d_idx < n:
                matrix[o_idx][d_idx] = _duration_to_seconds(element.get("duration"))
    return matrix


def _solve_open_tsp(matrix: List[List[Optional[int]]], delivery_count: int) -> List[int]:
    """Depodan (0) başlayıp tüm teslimatları minimum sürede ziyaret sırası.

    Returns:
        matrix indeksleri (1..delivery_count)
    """
    if delivery_count <= 0:
        return []
    if delivery_count == 1:
        return [1]

    stops = list(range(1, delivery_count + 1))
    best_order = stops
    best_seconds = None

    for perm in permutations(stops):
        total = matrix[0][perm[0]]
        if total is None:
            continue
        valid = True
        for idx in range(len(perm) - 1):
            leg = matrix[perm[idx]][perm[idx + 1]]
            if leg is None:
                valid = False
                break
            total += leg
        if not valid:
            continue
        if best_seconds is None or total < best_seconds:
            best_seconds = total
            best_order = list(perm)

    if best_seconds is None:
        raise UserError(
            _("Trafik matrisi tamamlanamadı; adresler Google tarafından çözülemedi.")
        )
    return best_order


def sort_deliveries_by_traffic(records) -> Tuple[int, int]:
    """Teslimat kayıtlarını trafik süresine göre sırala, sira_no güncelle.

    Args:
        records: teslimat.belgesi recordset (aynı araç + aynı gün)

    Returns:
        (sıralanan kayıt sayısı, tahmini toplam süre dakika)
    """
    records = records.exists()
    if not records:
        return 0, 0

    config = get_maps_route_config(records.env)
    if not config["api_key"]:
        raise UserError(
            _(
                "Google Maps API anahtarı tanımlı değil.\n\n"
                "Ayarlar → Teknik → Sistem Parametreleri → "
                "%(key)s"
            )
            % {"key": PARAM_API_KEY}
        )

    arac_ids = records.mapped("arac_id")
    tarihler = records.mapped("teslimat_tarihi")
    if len(arac_ids) != 1 or len(tarihler) != 1:
        raise UserError(
            _("Trafik sıralaması için aynı araç ve aynı teslimat tarihi seçilmelidir.")
        )

    active = records.filtered(
        lambda r: r.durum in ROTA_SIRALANABILIR_DURUMLAR
    ).sorted(key=lambda r: (r.sira_no, r.id))
    if not active:
        raise UserError(
            _("Sıralanacak teslimat yok (durum Hazır veya Yolda olmalı).")
        )

    if len(active) == 1:
        active.write({"sira_no": 1})
        return 1, 0

    adres_map = {}
    for rec in active:
        if not rec.musteri_id:
            raise UserError(
                _("%(name)s kaydında müşteri tanımlı değil.")
                % {"name": rec.name}
            )
        adres = prepare_maps_destination(rec.musteri_id)
        if not adres:
            raise UserError(
                _("%(name)s için harita adresi üretilemedi.")
                % {"name": rec.name}
            )
        adres_map[rec.id] = adres

    addresses = [config["depot"]] + [adres_map[r.id] for r in active]
    matrix = _fetch_travel_matrix(config["api_key"], addresses)
    order_indices = _solve_open_tsp(matrix, len(active))

    total_seconds = matrix[0][order_indices[0]] or 0
    for idx in range(len(order_indices) - 1):
        leg = matrix[order_indices[idx]][order_indices[idx + 1]]
        if leg:
            total_seconds += leg

    ordered_recs = [active[i - 1] for i in order_indices]

    for sira, rec in enumerate(ordered_recs, start=1):
        rec.write({"sira_no": sira})

    return len(ordered_recs), int(total_seconds / 60)


def cron_sort_today_deliveries(env) -> None:
    """Cron: bugünkü hazır/yolda teslimatları araç bazında sırala."""
    if not is_route_api_configured(env):
        _logger.info("Trafik rota cron: API anahtarı yok, atlandı")
        return

    Belge = env["teslimat.belgesi"]
    today_date = fields.Date.context_today(Belge)
    candidates = Belge.search(
        [
            ("teslimat_tarihi", "=", today_date),
            ("durum", "in", list(ROTA_SIRALANABILIR_DURUMLAR)),
        ]
    )
    for arac in candidates.mapped("arac_id"):
        arac_recs = candidates.filtered(lambda r: r.arac_id == arac)
        if len(arac_recs) < 2:
            continue
        try:
            count, minutes = sort_deliveries_by_traffic(arac_recs)
            _logger.info(
                "Trafik rota cron: %s / %s → %s teslimat, ~%s dk",
                arac.name,
                today_date,
                count,
                minutes,
            )
        except UserError as exc:
            _logger.warning(
                "Trafik rota cron atlandı (%s): %s",
                arac.name,
                exc.args[0] if exc.args else exc,
            )
        except Exception:
            _logger.exception("Trafik rota cron hatası: arac=%s", arac.name)
