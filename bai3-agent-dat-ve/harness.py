# -*- coding: utf-8 -*-
"""BTVN#3 · Lớp harness cho agent đặt vé. Ba mẫu agent dùng chung file này.

Bốn lớp theo đề bài:
    1. Ràng buộc là dữ liệu           YeuCau, vi_pham_rang_buoc
    2. Kiểm quyền                      kiem_quyen       (chạy TRƯỚC khi tool thực thi)
    3. Tiêu chí hoàn thành bằng code   kiem_hoan_thanh  (tự gọi get_booking, không tin lời model)
    4. Bàn giao                        ban_giao         (khi dừng bất thường)

Thêm hai điều kiện dừng: phát hiện lặp (LoopDetector, lấy từ demo buổi 03)
và ngân sách số lần gọi model. HarnessMiddleware cắm tất cả vào create_agent.

Chạy thử offline, không gọi API:  python harness.py
"""
import json
from collections import deque
from dataclasses import dataclass

from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.messages import AIMessage, ToolMessage

import tools_mock

HAN_MUC_TU_DUYET = 1_500_000        # agent chỉ tự đặt vé hoàn được và không quá mức này
NGAN_SACH_MODEL = 20                # số lần gọi model tối đa cho một yêu cầu
TOOL_DUOC_PHEP = {"search_flights", "check_seat", "book_seat", "pay", "get_booking", "write_todos"}
TOOL_CO_TAC_DUNG_PHU = {"book_seat", "pay"}


# ============================================== 1 · RÀNG BUỘC LÀ DỮ LIỆU
@dataclass(frozen=True)
class YeuCau:
    """Yêu cầu của khách, giữ ở một chỗ cố định. Prompt, kiểm quyền và
    tiêu chí hoàn thành đều đọc từ đây, không đọc lại từ lịch sử hội thoại."""
    di: str
    den: str
    ngay: str           # YYYY-MM-DD
    truoc_gio: str      # HH:MM, cất cánh trước giờ này
    tran_gia: int       # VND

    def mo_ta(self) -> str:
        return (f"- Tuyến: {self.di} → {self.den}\n"
                f"- Ngày bay: {self.ngay}\n"
                f"- Cất cánh trước {self.truoc_gio}\n"
                f"- Giá vé tối đa {self.tran_gia:,}đ")


def vi_pham_rang_buoc(chuyen: dict, yc: YeuCau) -> list:
    """Trả danh sách ràng buộc bị vi phạm; rỗng nghĩa là chuyến thoả yêu cầu."""
    vp = []
    if (chuyen["origin"], chuyen["destination"]) != (yc.di, yc.den):
        vp.append(f"sai tuyến {chuyen['origin']}→{chuyen['destination']}")
    if chuyen["date"] != yc.ngay:
        vp.append(f"sai ngày {chuyen['date']}")
    if chuyen["depart_time"] >= yc.truoc_gio:
        vp.append(f"giờ bay {chuyen['depart_time']} không trước {yc.truoc_gio}")
    if chuyen["price"] > yc.tran_gia:
        vp.append(f"giá {chuyen['price']:,}đ vượt trần {yc.tran_gia:,}đ")
    return vp


def cau_hoi_khach(yc: YeuCau) -> str:
    return (f"Đặt giúp tôi một vé {yc.di} → {yc.den} ngày {yc.ngay}, "
            f"cất cánh trước {yc.truoc_gio}, giá không quá {yc.tran_gia:,}đ.")


def system_prompt(yc: YeuCau) -> str:
    return ("Bạn là agent đặt vé máy bay cho nhân viên công ty.\n"
            "Yêu cầu của khách, phải thoả TẤT CẢ:\n" + yc.mo_ta() + "\n"
            "Quy tắc:\n"
            "- Chỉ dùng dữ liệu lấy từ tool, không tự bịa chuyến bay, giá, ghế hay mã booking.\n"
            "- Chọn chuyến rẻ nhất thoả yêu cầu và còn ghế.\n"
            "- Vé chỉ xong khi đã pay và get_booking trả booking_status = confirmed.\n"
            "- Nếu không có chuyến nào thoả thì dừng và nói rõ lý do, không đặt chuyến vi phạm yêu cầu.")


# ================================================== 2 · KIỂM QUYỀN
def _chuyen_cua(tool: str, args: dict):
    """Chuyến bay mà hành động book_seat / pay sắp tác động tới."""
    if tool == "book_seat":
        return tools_mock.tim_chuyen(args.get("flight_id", ""))
    b = tools_mock.BOOKINGS.get(str(args.get("booking_code", "")).strip().upper())
    return tools_mock.tim_chuyen(b["flight_id"]) if b else None


def kiem_quyen(tool: str, args: dict, yc: YeuCau):
    """Chạy trước khi tool thực thi. Trả (quyết định, lý do):

        OK         được làm
        CHAN       không được làm: tool lạ, hoặc chuyến trái ràng buộc của khách
        CAN_DUYET  hợp lệ nhưng vượt thẩm quyền của agent → dừng, chờ người duyệt
    """
    if tool not in TOOL_DUOC_PHEP:
        return "CHAN", [f"tool '{tool}' không có trong danh sách được phép"]
    if tool not in TOOL_CO_TAC_DUNG_PHU:
        return "OK", []
    chuyen = _chuyen_cua(tool, args)
    if chuyen is None:
        return "OK", []                 # để tool tự trả not_found kèm hint
    vp = vi_pham_rang_buoc(chuyen, yc)
    if vp:
        return "CHAN", vp
    ly_do = []
    if chuyen["price"] > HAN_MUC_TU_DUYET:
        ly_do.append(f"giá {chuyen['price']:,}đ vượt hạn mức tự duyệt {HAN_MUC_TU_DUYET:,}đ")
    if not chuyen["refundable"]:
        ly_do.append("vé không hoàn được")
    return ("CAN_DUYET", ly_do) if ly_do else ("OK", [])


# ====================================== 3 · TIÊU CHÍ HOÀN THÀNH BẰNG CODE
def kiem_hoan_thanh(yc: YeuCau, quan_sat: list) -> dict:
    """Đạt khi có booking confirmed, đã trả tiền và thoả mọi ràng buộc.

    Mã booking lấy từ kết quả book_seat; trạng thái thì harness TỰ đọc lại bằng
    get_booking (kiểm chứng chéo), không dựa vào câu trả lời của model.
    """
    codes = list(dict.fromkeys(o["booking_code"] for o in quan_sat if o.get("status") == "held"))
    if not codes:
        return {"dat": False, "booking": None, "loi": ["chưa có booking nào"]}
    loi = []
    for code in codes:
        b = tools_mock.get_booking(code)
        sai = []
        if b.get("booking_status") != "confirmed":
            sai.append(f"trạng thái {b.get('booking_status')}")
        if not b.get("paid"):
            sai.append("chưa thanh toán")
        sai += vi_pham_rang_buoc(b, yc)
        if not sai:
            return {"dat": True, "booking": b, "loi": []}
        loi.append(f"{code}: " + ", ".join(sai))
    return {"dat": False, "booking": None, "loi": loi}


# ================================================== 4 · BÀN GIAO
def ban_giao(ly_do: str, da_thu: list, trang_thai: dict, cau_hoi: str) -> dict:
    """Dừng bất thường thì bàn giao đủ thông tin cho người, không dừng im lặng."""
    return {"stop_reason": ly_do,
            "da_thu": da_thu,
            "trang_thai": trang_thai,
            "cau_hoi_cho_nguoi": cau_hoi}


def trang_thai_hien_tai() -> dict:
    """Ảnh chụp tác dụng phụ đã xảy ra: booking nào đã giữ chỗ, đã trả tiền."""
    ds = [f"{b['booking_code']} {b['flight_id']} ghế {b['seat']} · {b['status']}"
          + (" · đã trả tiền" if b["paid"] else " · chưa trả tiền")
          for b in tools_mock.BOOKINGS.values()]
    return {"tac_dung_phu": ds or ["chưa có (chưa giữ chỗ, chưa trả tiền)"]}


def in_ban_giao(b: dict) -> str:
    return ("DỪNG BẤT THƯỜNG · " + b["stop_reason"] + "\n"
            "  Đã thử     : " + (" → ".join(b["da_thu"]) or "(chưa gọi tool nào)") + "\n"
            "  Trạng thái : " + "; ".join(b["trang_thai"]["tac_dung_phu"]) + "\n"
            "  Hỏi người  : " + b["cau_hoi_cho_nguoi"])


# ============================================ ĐIỀU KIỆN DỪNG PHỤ TRỢ
class LoopDetector:
    """Lấy từ demo buổi 03 (lib/harness.py), chỉ giữ tín hiệu trùng (tool, args).

    So action chứ không so observation: gọi lại get_booking để chờ confirmed là hợp lệ.
    """

    def __init__(self, window=6, repeat_k=3):
        self.recent = deque(maxlen=window)
        self.k = repeat_k

    def check(self, tool: str, args: dict):
        fp = (tool, repr(sorted(args.items())))
        n = self.recent.count(fp) + 1
        self.recent.append(fp)
        if n >= self.k:
            return f"LOOP · '{tool}' gọi {n} lần với cùng tham số trong {self.recent.maxlen} lượt gần nhất"
        return None


# ========================================== CẮM VÀO LANGCHAIN
def _args(args: dict) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in args.items())


def _doc(content):
    try:
        return json.loads(content)
    except Exception:
        return content


class HarnessMiddleware(AgentMiddleware):
    """Checklist harness chạy quanh mỗi vòng (slide "Checklist harness chạy sau mỗi vòng"):

        after_model     0 · kiểm quyền (CAN_DUYET → dừng chờ người, tool không chạy)
                        2 · phát hiện lặp
        wrap_tool_call  kiểm quyền (CHAN → không thực thi, trả observation có lý do)
                        ghi observation cho tiêu chí hoàn thành
        before_model    4 · ngân sách, kiểm cuối cùng
    Tiêu chí hoàn thành (1) chạy trong ket_thuc(), sau khi model tự dừng.
    """

    def __init__(self, yc: YeuCau):
        super().__init__()
        self.yc = yc
        self.loop = LoopDetector()
        self.so_goi_model = 0
        self.so_goi_tool = 0            # chỉ đếm 5 tool đặt vé, không đếm write_todos
        self.tokens = 0
        self.so_lan_chan = 0
        self.da_thu = []                # hành động đã thử, dùng khi bàn giao
        self.quan_sat = []              # observation dạng dict, dùng cho tiêu chí hoàn thành
        self.trace = []
        self.dung = None                # (loại, bàn giao) khi harness dừng bất thường

    def dem_model(self, ai) -> None:
        self.so_goi_model += 1
        self.tokens += (getattr(ai, "usage_metadata", None) or {}).get("total_tokens", 0)

    def dung_lai(self, loai: str, ly_do: str, cau_hoi: str) -> dict:
        self.dung = (loai, ban_giao(ly_do, list(self.da_thu), trang_thai_hien_tai(), cau_hoi))
        self.trace.append("[HARNESS] " + ly_do)
        return {"jump_to": "end", "messages": [AIMessage(content=in_ban_giao(self.dung[1]))]}

    @hook_config(can_jump_to=["end"])
    def before_model(self, state, runtime):
        if self.dung:
            return {"jump_to": "end"}
        if self.so_goi_model >= NGAN_SACH_MODEL:
            return self.dung_lai("BAN_GIAO", f"BUDGET · đã dùng hết {NGAN_SACH_MODEL} lượt gọi model",
                                 "Agent chưa xong trong ngân sách. Tiếp tục thủ công từ trạng thái trên, "
                                 "hay tăng ngân sách?")
        return None

    @hook_config(can_jump_to=["end"])
    def after_model(self, state, runtime):
        ai = state["messages"][-1]
        self.dem_model(ai)
        calls = getattr(ai, "tool_calls", None) or []
        if not calls:
            self.trace.append(f"[V{self.so_goi_model}] AI   : {str(ai.content)[:300]}")
        for c in calls:
            ten, args = c["name"], c["args"]
            self.trace.append(f"[V{self.so_goi_model}] AI   → {ten}({_args(args)})")
            quyet_dinh, ly_do = kiem_quyen(ten, args, self.yc)
            if quyet_dinh == "CAN_DUYET":
                ch = _chuyen_cua(ten, args)
                return self.dung_lai(
                    "CAN_NGUOI", f"CẦN DUYỆT · {ten}({_args(args)}): " + "; ".join(ly_do),
                    f"Duyệt đặt chuyến {ch['flight_id']} {ch['date']} {ch['depart_time']} giá {ch['price']:,}đ "
                    f"({'hoàn được' if ch['refundable'] else 'không hoàn'}) không?")
            if ten != "write_todos":
                canh_bao = self.loop.check(ten, args)
                if canh_bao:
                    return self.dung_lai("BAN_GIAO", canh_bao,
                                         "Agent lặp cùng một hành động. Kiểm tra dữ liệu chuyến bay, "
                                         "hay đổi yêu cầu?")
        return None

    def wrap_tool_call(self, request, handler):
        c = request.tool_call
        ten, args = c["name"], c["args"]
        quyet_dinh, ly_do = kiem_quyen(ten, args, self.yc)
        if quyet_dinh == "CHAN":
            self.so_lan_chan += 1
            obs = {"status": "rejected_by_harness", "violations": ly_do,
                   "hint": "Chọn chuyến khác thoả yêu cầu, hoặc dừng và báo không có chuyến phù hợp"}
            self.da_thu.append(f"{ten}({_args(args)}) → BỊ CHẶN")
            self.trace.append(f"         ← [HARNESS CHẶN] {'; '.join(ly_do)}")
            return ToolMessage(content=json.dumps(obs, ensure_ascii=False), tool_call_id=c["id"], name=ten)

        kq = handler(request)
        if not isinstance(kq, ToolMessage):         # write_todos trả Command, không phải observation
            self.trace.append(f"         ← (cập nhật todo)")
            return kq
        obs = _doc(kq.content)
        self.so_goi_tool += 1
        if isinstance(obs, dict):
            self.quan_sat.append(obs)
        trang_thai = obs.get("status", "?") if isinstance(obs, dict) else "?"
        self.da_thu.append(f"{ten}({_args(args)}) → {trang_thai}")
        self.trace.append(f"         ← {str(kq.content)[:220]}")
        return kq


def ket_thuc(h: HarnessMiddleware, tra_loi: str) -> dict:
    """Chốt kết quả một lần chạy, giống nhau cho cả ba mẫu.

    Harness đã dừng bất thường → trả bàn giao. Model tự dừng → chưa tin, chạy
    tiêu chí hoàn thành bằng code; không đạt thì cũng chuyển thành bàn giao.
    """
    if h.dung:
        loai, bg = h.dung
        ly_do = bg["stop_reason"]
    else:
        kt = kiem_hoan_thanh(h.yc, h.quan_sat)
        if kt["dat"]:
            b = kt["booking"]
            loai, bg = "DAT", None
            ly_do = f"ĐẠT · {b['booking_code']} {b['flight_id']} {b['depart_time']} {b['price']:,}đ confirmed"
        else:
            loai = "BAN_GIAO"
            ly_do = "CHƯA ĐẠT TIÊU CHÍ HOÀN THÀNH · " + "; ".join(kt["loi"])
            bg = ban_giao(ly_do, list(h.da_thu), trang_thai_hien_tai(),
                          "Không đặt được vé thoả mọi yêu cầu. Nới giá trần hoặc giờ bay, đổi ngày, "
                          "hay huỷ yêu cầu?")
    vi_pham = [b for b in tools_mock.BOOKINGS.values()
               if vi_pham_rang_buoc(tools_mock.get_booking(b["booking_code"]), h.yc)]
    return {"ket_qua": loai, "ly_do_dung": ly_do, "ban_giao": bg, "tra_loi": tra_loi,
            "so_goi_model": h.so_goi_model, "so_goi_tool": h.so_goi_tool, "tokens": h.tokens,
            "so_lan_chan": h.so_lan_chan, "booking_vi_pham": len(vi_pham), "trace": h.trace}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    yc = YeuCau("SGN", "DAD", "2026-10-07", "12:00", 2_000_000)

    print("── Kiểm quyền (trước khi tool chạy) ──")
    for tool, args in [("book_seat", {"flight_id": "VJ122", "seat": "12A"}),   # hợp lệ, trong hạn mức
                       ("book_seat", {"flight_id": "VN126", "seat": "20A"}),   # bay chiều → trái ràng buộc
                       ("book_seat", {"flight_id": "VN120", "seat": "3A"}),    # 1.650.000 > hạn mức
                       ("delete_booking", {"booking_code": "BK001"})]:        # tool lạ
        print(f"  {tool}({_args(args)}) → {kiem_quyen(tool, args, yc)}")

    print("\n── Tiêu chí hoàn thành (kiểm bằng code) ──")
    tools_mock.reset()
    obs = [tools_mock.book_seat("VJ122", "12A")]
    print("  sau book_seat :", kiem_hoan_thanh(yc, obs))
    tools_mock.pay(obs[0]["booking_code"])
    print("  sau pay       :", kiem_hoan_thanh(yc, obs))

    print("\n── LoopDetector ──")
    det = LoopDetector()
    for vong in range(1, 4):
        print(f"  V{vong} check_seat('VJ130') → {det.check('check_seat', {'flight_id': 'VJ130'}) or 'bình thường'}")

    print("\n── Bàn giao ──")
    print(in_ban_giao(ban_giao("CẦN DUYỆT · book_seat(VN140): vé không hoàn được",
                               ["search_flights(...) → ok", "check_seat(VN140) → ok"],
                               trang_thai_hien_tai(), "Duyệt đặt chuyến VN140 không?")))
