# -*- coding: utf-8 -*-
"""BTVN#3 · Đánh giá ba mẫu agent trên bốn kịch bản.

    python danh_gia.py            # 4 kịch bản × 3 mẫu × 3 lần
    python danh_gia.py --lap 1    # chạy nhanh

Kết quả: ket_qua_danh_gia.md (bảng) và ket_qua_danh_gia.json (kèm trace từng lần chạy).
Một lần chạy "đúng" khi kết quả khớp kỳ vọng và không có booking nào vi phạm ràng buộc.
"""
import argparse
import json
import sys
from pathlib import Path

from harness import YeuCau

# Kịch bản cũng là dữ liệu: yêu cầu của khách + kết quả mong đợi.
KICH_BAN = {
    1: {"ten": "Bình thường",
        "yeu_cau": YeuCau("SGN", "DAD", "2026-10-07", "12:00", 2_000_000), "ky_vong": "DAT"},
    2: {"ten": "Chuyến rẻ nhất hết chỗ",
        "yeu_cau": YeuCau("SGN", "HAN", "2026-10-08", "12:00", 2_000_000), "ky_vong": "DAT"},
    3: {"ten": "Chỉ còn vé không hoàn, vượt hạn mức",
        "yeu_cau": YeuCau("SGN", "PQC", "2026-10-09", "12:00", 2_000_000), "ky_vong": "CAN_NGUOI"},
    4: {"ten": "Không có chuyến thoả",
        "yeu_cau": YeuCau("SGN", "HUI", "2026-10-10", "12:00", 2_000_000), "ky_vong": "BAN_GIAO"},
}
TEN_MAU = {"react": "ReAct", "plan": "Plan-then-Execute", "lai": "Lai"}
DIR = Path(__file__).parent


def _tb(rows, key):
    return round(sum(r[key] for r in rows) / len(rows), 1) if rows else 0


def ghi_bao_cao(rows: list, lap: int) -> str:
    out = [f"# Kết quả đánh giá ({lap} lần mỗi cặp mẫu × kịch bản)\n",
           "## Tổng hợp theo mẫu\n",
           "| Mẫu | Đúng kỳ vọng | Gọi model TB | Gọi tool TB | Token TB | Thời gian TB (s) | Harness chặn | Booking vi phạm |",
           "|---|---|---|---|---|---|---|---|"]
    for m, ten in TEN_MAU.items():
        r = [x for x in rows if x["mau"] == m]
        if not r:
            continue
        out.append(f"| {ten} | {sum(x['dung'] for x in r)}/{len(r)} | {_tb(r, 'so_goi_model')} | "
                   f"{_tb(r, 'so_goi_tool')} | {_tb(r, 'tokens'):.0f} | {_tb(r, 'giay')} | "
                   f"{sum(x['so_lan_chan'] for x in r)} | {sum(x['booking_vi_pham'] for x in r)} |")

    out += ["\n## Theo kịch bản (số lần đúng kỳ vọng)\n",
            "| Kịch bản | Kỳ vọng | " + " | ".join(TEN_MAU.values()) + " |",
            "|---|---|" + "---|" * len(TEN_MAU)]
    for k, kb in KICH_BAN.items():
        o = []
        for m in TEN_MAU:
            r = [x for x in rows if x["mau"] == m and x["kich_ban"] == k]
            o.append(f"{sum(x['dung'] for x in r)}/{len(r)}" if r else "-")
        out.append(f"| {k}. {kb['ten']} | {kb['ky_vong']} | " + " | ".join(o) + " |")

    out += ["\n## Chi tiết từng lần chạy\n",
            "| Mẫu | KB | Lần | Kết quả | Đúng? | Model | Tool | Token | Giây | Lý do dừng |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for x in rows:
        ly_do = x["ly_do_dung"].replace("|", "/")[:150]
        out.append(f"| {TEN_MAU[x['mau']]} | {x['kich_ban']} | {x['lan']} | {x['ket_qua']} | "
                   f"{'✅' if x['dung'] else '❌'} | {x['so_goi_model']} | {x['so_goi_tool']} | "
                   f"{x['tokens']} | {x['giay']} | {ly_do} |")
    return "\n".join(out) + "\n"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    from agents import MAU, chay, tao_model

    p = argparse.ArgumentParser(description="Đánh giá 3 mẫu agent đặt vé")
    p.add_argument("--lap", type=int, default=3)
    p.add_argument("--mau", choices=list(MAU), nargs="*", default=list(MAU))
    p.add_argument("--kich-ban", type=int, choices=list(KICH_BAN), nargs="*", default=list(KICH_BAN))
    a = p.parse_args()

    model = tao_model()
    rows = []
    for m in a.mau:
        for k in a.kich_ban:
            kb = KICH_BAN[k]
            for lan in range(1, a.lap + 1):
                try:
                    kq = chay(m, kb["yeu_cau"], model)
                except Exception as e:          # lỗi API/mạng: ghi lại, không dừng cả đợt đánh giá
                    kq = {"mau": m, "ket_qua": "LOI", "ly_do_dung": f"{type(e).__name__}: {e}",
                          "so_goi_model": 0, "so_goi_tool": 0, "tokens": 0, "giay": 0,
                          "so_lan_chan": 0, "booking_vi_pham": 0, "trace": [], "ban_giao": None,
                          "tra_loi": ""}
                kq.update(kich_ban=k, lan=lan,
                          dung=kq["ket_qua"] == kb["ky_vong"] and kq["booking_vi_pham"] == 0)
                rows.append(kq)
                print(f"{TEN_MAU[m]:<18} KB{k} lần {lan}: {kq['ket_qua']:<10} "
                      f"{'đúng' if kq['dung'] else 'SAI '} · model {kq['so_goi_model']:>2} · "
                      f"tool {kq['so_goi_tool']:>2} · {kq['giay']}s · {kq['ly_do_dung'][:70]}", flush=True)

    (DIR / "ket_qua_danh_gia.md").write_text(ghi_bao_cao(rows, a.lap), encoding="utf-8")
    (DIR / "ket_qua_danh_gia.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                                               encoding="utf-8")
    print("\nĐã ghi ket_qua_danh_gia.md và ket_qua_danh_gia.json")


if __name__ == "__main__":
    main()
