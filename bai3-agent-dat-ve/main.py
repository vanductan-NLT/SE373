# -*- coding: utf-8 -*-
"""BTVN#3 · Chạy một mẫu agent trên một kịch bản và in trace.

    python main.py --mau react --kich-ban 1
    python main.py --mau plan  --kich-ban 2
    python main.py --mau lai   --kich-ban 3
"""
import argparse
import sys

from agents import MAU, chay, tao_model
from danh_gia import KICH_BAN, TEN_MAU
from harness import in_ban_giao


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Agent đặt vé máy bay")
    p.add_argument("--mau", choices=list(MAU), default="react")
    p.add_argument("--kich-ban", type=int, choices=list(KICH_BAN), default=1)
    a = p.parse_args()

    kb = KICH_BAN[a.kich_ban]
    print("=" * 78)
    print(f"{TEN_MAU[a.mau]} · Kịch bản {a.kich_ban}: {kb['ten']} (kỳ vọng {kb['ky_vong']})")
    print(kb["yeu_cau"].mo_ta())
    print("=" * 78)

    kq = chay(a.mau, kb["yeu_cau"], tao_model())

    print("\n".join(kq["trace"]))
    print("-" * 78)
    print(f"Kết quả  : {kq['ket_qua']} ({'khớp' if kq['ket_qua'] == kb['ky_vong'] else 'KHÔNG khớp'} kỳ vọng)")
    print(f"Lý do    : {kq['ly_do_dung']}")
    print(f"Chi phí  : {kq['so_goi_model']} lần gọi model · {kq['so_goi_tool']} lần gọi tool · "
          f"{kq['tokens']} token · {kq['giay']}s · harness chặn {kq['so_lan_chan']} lần")
    if kq["ban_giao"]:
        print("-" * 78)
        print(in_ban_giao(kq["ban_giao"]))


if __name__ == "__main__":
    main()
