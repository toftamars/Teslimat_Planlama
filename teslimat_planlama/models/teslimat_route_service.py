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
DEFAULT_DEPOT_ADDRESS = (
    "İstanbul, Türkiye"
)
ROTA_SIRALANABILIR_DURUMLAR = ("hazir", "yolda")


def ensure_maps_config_parameters(env) -> None:
    """Sistem parametrelerini yalnızca yoksa oluştur (manuel kayıtları ezmez)."""
    icp = env["ir.config_parameter"].sudo()
    if not icp.search([("key", "=", PARAM_API_KEY)], limit=1):
        icp.set_param(PARAM_API_KEY, "")
    if not icp.search([("key", "=", PARAM_DEPOT)], limit=1):
        icp.set_param(PARAM_DEPOT, DEFAULT_DEPOT_ADDRESS)


def get_maps_route_config(env) -> dict:
    """Sistem parametrelerinden rota yapılandırmasını oku."""
    icp = env["ir.config_parameter"].sudo()
    return {
        "api_key": (icp.get_param(PARAM_API_KEY) or "").strip(),
        "depot": (icp.get_param(PARAM_DEPOT) or "").strip()
        or DEFAULT_DEPOT_ADDRESS,
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


def get_rota_optimizasyon_groups(env, selected_records=None):
    """Araç + gün bazında sıralanacak tam teslimat grupları.

    Seçim yoksa bugünkü tüm hazır/yolda teslimatlar.
    Seçim varsa ilgili her araç+gün için o günkü TÜM teslimatlar.
    """
    Belge = env["teslimat.belgesi"]
    durumlar = list(ROTA_SIRALANABILIR_DURUMLAR)

    if selected_records:
        keys = {
            (rec.arac_id.id, rec.teslimat_tarihi)
            for rec in selected_records
            if rec.arac_id
            and rec.teslimat_tarihi
            and rec.durum in ROTA_SIRALANABILIR_DURUMLAR
        }
        if not keys:
            raise UserError(
                _(
                    "Seçili kayıtlarda sıralanacak teslimat yok.\n\n"
                    "Durum Hazır veya Yolda olan teslimatları seçin."
                )
            )
    else:
        today = fields.Date.context_today(Belge)
        keys = {
            (rec.arac_id.id, rec.teslimat_tarihi)
            for rec in Belge.search(
                [
                    ("teslimat_tarihi", "=", today),
                    ("durum", "in", durumlar),
                ]
            )
            if rec.arac_id
        }
        if not keys:
            raise UserError(
                _(
                    "Bugün sıralanacak teslimat bulunamadı.\n\n"
                    "Hazır veya Yolda durumunda teslimat olmalı."
                )
            )

    result = []
    Arac = env["teslimat.arac"]
    for arac_id, tarih in sorted(keys, key=lambda k: (k[1], k[0])):
        group = Belge.search(
            [
                ("arac_id", "=", arac_id),
                ("teslimat_tarihi", "=", tarih),
                ("durum", "in", durumlar),
            ]
        )
        if group:
            result.append(
                {
                    "records": group,
                    "arac_name": Arac.browse(arac_id).display_name,
                    "teslimat_tarihi": tarih,
                }
            )
    if not result:
        raise UserError(_("Sıralanacak teslimat grubu bulunamadı."))
    return result


def _sort_single_vehicle_day(records) -> Tuple[int, int]:
    """Tek araç + tek gün teslimatlarını trafik süresine göre sırala."""
    records = records.exists()
    if not records:
        return 0, 0

    config = get_maps_route_config(records.env)
    active = records.filtered(
        lambda r: r.durum in ROTA_SIRALANABILIR_DURUMLAR
    ).sorted(key=lambda r: (r.sira_no, r.id))
    if not active:
        return 0, 0

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


def sort_vehicle_day_deliveries(records) -> Tuple[int, int]:
    """Tek araç + tek gün teslimatlarını trafik süresine göre sırala."""
    return _sort_single_vehicle_day(records)


def sort_deliveries_by_traffic(records) -> Tuple[int, int]:
    """Teslimatları araç+gün grupları halinde trafik sırasına göre sırala."""
    env = records.env
    config = get_maps_route_config(env)
    if not config["api_key"]:
        raise UserError(
            _(
                "Google Maps API anahtarı tanımlı değil.\n\n"
                "Ayarlar → Teknik → Sistem Parametreleri → "
                "%(key)s"
            )
            % {"key": PARAM_API_KEY}
        )

    groups = get_rota_optimizasyon_groups(
        env, selected_records=records if records else None
    )
    total_count = 0
    total_minutes = 0
    for entry in groups:
        count, minutes = _sort_single_vehicle_day(entry["records"])
        total_count += count
        total_minutes += minutes
    return total_count, total_minutes


def cron_sort_today_deliveries(env) -> None:
    """Cron: bugünkü hazır/yolda teslimatları araç bazında sırala."""
    if not is_route_api_configured(env):
        _logger.info("Trafik rota cron: API anahtarı yok, atlandı")
        return

    try:
        count, minutes = sort_deliveries_by_traffic(env["teslimat.belgesi"].browse())
        _logger.info(
            "Trafik rota cron: %s teslimat sıralandı, ~%s dk",
            count,
            minutes,
        )
    except UserError as exc:
        _logger.warning(
            "Trafik rota cron atlandı: %s",
            exc.args[0] if exc.args else exc,
        )
    except Exception:
        _logger.exception("Trafik rota cron hatası")
